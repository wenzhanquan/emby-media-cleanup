# Emby Media Cleanup

为 **Immortal + MDCNG + CloudDrive2（CD2）+ Emby** 部署提供每周清理容器。运行状态、下次执行时间和结果可直接在 NAS 的 Docker 容器日志中查看。

## 清理规则

- 仅处理指定 Emby 电影媒体库，默认路径 `/media/strm/小姐姐`。
- 删除可识别的 VR 影片，不受演员保护规则限制。
- 非 VR 影片：入库时间超过 **三个自然月**，且没有任何 Immortal 订阅演员参演时才清理。
- 每次执行都读取 Immortal 当前演员订阅，通过演员 ID、影片番号、日文名、中文名和 MDCNG 别名映射保护影片。含任意一位订阅演员即保留。
- 缺少演员或入库时间、目录对应不明确、目录混放、嵌套目录、符号链接或非预期文件类型，均保留并记录。
- 先删除 Emby 条目并确认移除，再删除对应 115 视频、本地 STRM 和配套文件。**这是实际删除，不是归档或仅隐藏条目。**

默认每周日 **04:30，Asia/Shanghai** 执行。停止容器即可暂停；重启不会额外执行一轮。已记录但错过的执行周期会在恢复后补执行一次。

## 镜像与自动构建

```sh
docker pull ghcr.io/wenzhanquan/emby-media-cleanup:latest
```

推送 `main` 分支时，GitHub Actions 先运行测试，再自动构建并发布 `linux/amd64` 和 `linux/arm64` 镜像到 GHCR。推送 `v1.0.0` 这样的标签时，同时发布 `1.0.0` 版本镜像。不需要额外的 Docker Hub 密码或仓库密钥。

本仓库包含全部运行脚本，镜像使用公开 Python 基础镜像，不依赖 NAS 上的自制基础镜像。即使 NAS 原有脚本丢失，也可重新下载 Compose 文件并拉取镜像部署。

GHCR 新建包的可见性可能默认为私有：若匿名拉取返回 `denied`，仓库所有者需在 GitHub 的 Packages → emby-media-cleanup → Package settings → Change visibility 中设为 Public。私有包则需要先 `docker login ghcr.io`。

## 部署

```sh
git clone https://github.com/wenzhanquan/emby-media-cleanup.git
cd emby-media-cleanup
cp .env.example .env
# 根据实际 NAS 目录修改 .env
docker compose up -d
docker logs emby-media-cleanup
```

在飞牛等 NAS 的 Docker Compose 项目中，也可直接使用本仓库 `docker-compose.yml` 和填写后的 `.env`。在 Docker 容器列表中查找 **emby-media-cleanup**。

### 路径配置

`.env.example` 的 NAS 路径只是示例，应按自己的部署修改：

| 变量 | 含义 |
|---|---|
| `HOST_DATA_ROOT` | NAS 数据父目录；其中应有 `strm/小姐姐` 和 `115open/strm/小姐姐` |
| `MDC_DATA_DIR` | MDCNG 的 data 目录，必须含 `mapping_actor.xml` |
| `AUDIT_DIR` | 持久化清理清单和逐目录执行记录；可指向旧部署目录以保留历史 |
| `IMMORTAL_CONTAINER` | Immortal 容器名，默认 `immortal` |
| `EMBY_LIBRARY_PATH` | Emby 容器里看到的媒体库根路径，默认 `/media/strm/小姐姐` |
| `CLEANUP_WEEKDAY` | 0=周一，…，6=周日 |
| `CLEANUP_HOUR` / `CLEANUP_MINUTE` | 北京时间的执行时、分 |
| `IMAGE` | 镜像地址，默认 GHCR latest，也可固定版本 |

容器内部可通过 `LOCAL_MEDIA_ROOT`、`CLOUD_MEDIA_ROOT`、`ACTOR_MAPPING`、`AUDIT_ROOT` 覆盖默认位置；这些覆盖值必须是容器内部路径。实际删除前会核对 STRM 和对应视频的文件名，无法匹配的目录不会删除。

### 前提与权限

- Immortal 已配置 `MediaServer.emby`，且其 Emby API Key 允许删除影片；不必把密钥填写到本项目。
- 需要能访问 Immortal 使用的数据库，以及 Emby 的配置地址。默认使用 host 网络，适用于 Linux NAS。
- CD2 已将网盘挂载到 NAS。父目录以 `rslave` 传入，接收之后的挂载变化。无法访问的网盘目录会跳过。
- Docker socket 用于在 Immortal 容器中执行只读查询。**Docker socket 权限等价于高权限 Docker 控制**，`:ro` 不会限制 API 能力；仅在信任脚本的 NAS 上部署。
- 视频与本地 STRM 使用对应的独立影片目录；不支持只知道 HTTP 链接但无法定位实际文件的部署。

## 日常使用

查看日志和下次执行时间：

```sh
docker logs --tail 100 emby-media-cleanup
```

先做只读预检查，**不会删除文件**：

```sh
docker exec emby-media-cleanup python /opt/media-cleanup/cleanup.py
```

立即执行清理，**会删除实际视频**：

```sh
docker exec emby-media-cleanup python -u /opt/media-cleanup/cleanup.py --apply
```

暂停及恢复：

```sh
docker stop emby-media-cleanup
docker start emby-media-cleanup
```

更新镜像：

```sh
docker compose pull
docker compose up -d
```

Watchtower 自动更新默认关闭，更新由管理员手动选择。更改 `.env` 后执行 `docker compose up -d`。

## 审计、失败处理和恢复

每轮执行前在 `AUDIT_DIR` 写入日期命名的 JSON 清单，每个目录的执行阶段写入同名 JSONL。调度状态位于项目 `state/scheduler-status.json`。清理互斥锁避免同时启动两轮。

如果 Emby 删除成功后，网盘删除失败，影片可能已从 Emby 消失而实际文件仍保留。必须查看 JSONL 中的 `error` 和 `emby_removed` 记录，核对文件后手工处理；不能仅凭任务退出码判断每个目录都完成。保存好审计目录。删除的文件不能靠重新拉取镜像恢复；是否可恢复取决于网盘回收站等外部机制。

从旧 systemd 部署迁移时，验证容器只读预检查通过后，停用旧定时器，避免两套调度重复执行：

```sh
sudo systemctl disable --now nas-media-cleanup.timer
```

## 开发验证

```sh
python -m unittest discover -v
docker build -t emby-media-cleanup:test .
```

测试覆盖月份边界、订阅演员保护、未知演员保留、VR 排除、文件变化及 Emby 删除失败时保留实际文件、每周调度和 Docker 输出流解析。没有为了验证部署而自动重放真实影片删除。
