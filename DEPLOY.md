# 🚀 作业小龙 — Windows 云服务器部署指南

本指南帮助你将作业小龙部署到 Windows 云服务器，面向公网访问。适用于 Windows Server 2019+ / Windows 10+。

---

## 目录

1. [服务器要求](#1-服务器要求)
2. [安装 Python 环境](#2-安装-python-环境)
3. [部署代码](#3-部署代码)
4. [启动服务](#4-启动服务)
5. [配置 OpenResty 反向代理](#5-配置-openresty-反向代理)
6. [（可选）配置 HTTPS 自签证书](#6-可选配置-https-自签证书)
8. [配置 NSSM 开机自启](#8-配置-nssm-开机自启)
9. [配置定时任务](#9-配置定时任务)
10. [数据备份](#10-数据备份)
11. [防火墙配置](#11-防火墙配置)
12. [版本升级](#12-版本升级)
13. [常见问题](#13-常见问题)

---

## 1. 服务器要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 1 核 | 2 核 |
| 内存 | 1GB | 2GB+ |
| 硬盘 | 20GB | 40GB |
| 系统 | Windows Server 2019 | Windows Server 2022 |
| 网络 | 公网 IP + 可用端口 | 带宽 ≥ 1Mbps |

> 本项目为轻量级应用（FastAPI + SQLite），入门级云服务器即可运行。

---

## 2. 安装 Python 环境

### 2.1 下载安装

从官网下载 Python 3.11+ 安装包：

```
https://www.python.org/downloads/
```

安装时 **务必勾选**：
- ✅ `Add Python to PATH`
- ✅ `pip`

### 2.2 验证安装

以 **管理员身份** 打开 PowerShell，执行：

```powershell
python --version      # 需要 3.8+，推荐 3.11+
pip --version
```

### 2.3 配置虚拟环境（可选但推荐）

```powershell
# 升级 pip
python -m pip install --upgrade pip
```

---

## 3. 部署代码

### 方式一：Git 克隆（推荐）

```powershell
# 确保已安装 Git：https://git-scm.com/download/win

# 创建项目目录
New-Item -Path "C:\homework-pet" -ItemType Directory -Force
Set-Location "C:\homework-pet"

# 克隆代码
git clone https://github.com/your-repo/homework-pet.git .

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

> **PowerShell 执行策略**：如果激活虚拟环境时报错，先执行：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 方式二：手动上传

1. 在本地将项目文件夹压缩为 `homework-pet.zip`
2. 通过远程桌面（RDP）或 FTP 上传到服务器 `C:\` 目录
3. 右键 → 解压到 `C:\homework-pet`
4. 打开 PowerShell：

```powershell
Set-Location "C:\homework-pet"

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

---

## 4. 启动服务

### 4.1 测试启动

```powershell
Set-Location "C:\homework-pet\app"

# 激活虚拟环境
C:\homework-pet\venv\Scripts\Activate.ps1

# 测试启动
python -m uvicorn main:app --host 127.0.0.1 --port 5000
```

看到以下输出说明启动成功：
```
INFO:     Uvicorn running on http://127.0.0.1:5000
INFO:     Started reloader process [xxxxx]
INFO:     Started server process [xxxxx]
INFO:     Application startup complete.
```

按 `Ctrl+C` 停止测试服务。

### 4.2 使用 Uvicorn 直接启动（生产环境）

Windows 上推荐直接使用 Uvicorn（Gunicorn 不支持 Windows）。多进程方案见 [第 8 节 NSSM 配置](#8-配置-nssm-开机自启)。

```powershell
Set-Location "C:\homework-pet\app"
C:\homework-pet\venv\Scripts\Activate.ps1

# 生产模式启动（不使用 reload）
python -m uvicorn main:app --host 127.0.0.1 --port 5000 --workers 2
```

> **注意**：生产环境中绑定 `127.0.0.1`（仅本地），由 OpenResty 转发外部请求。不要直接绑定 `0.0.0.0`。

---

## 5. 配置 OpenResty 反向代理

腾讯云 Windows 镜像通常预装了 **OpenResty**（增强版 Nginx，配置语法完全相同）。如果你的服务器访问 80 端口显示 "Welcome to OpenResty!" 页面，说明已安装。

### 5.1 确认 OpenResty 安装路径

```powershell
# 查找 OpenResty 安装位置
Get-Command nginx -ErrorAction SilentlyContinue
Get-ChildItem "C:\" -Directory -Filter "*openresty*" -ErrorAction SilentlyContinue
Get-ChildItem "C:\" -Directory -Filter "*nginx*" -ErrorAction SilentlyContinue

# 常见路径
# C:\openresty\
# C:\nginx\
# D:\openresty\
```

确认找到 OpenResty 目录后，记下路径，下文统一用 `C:\openresty` 表示（请根据实际情况替换）。

### 5.2 基本命令

```powershell
# 启动 OpenResty
Start-Process "C:\openresty\nginx.exe"

# 停止 OpenResty
Stop-Process -Name nginx -Force

# 重新加载配置（不停机）
C:\openresty\nginx.exe -s reload

# 测试配置文件语法
C:\openresty\nginx.exe -t

# 查看版本
C:\openresty\nginx.exe -v
```

### 5.3 编辑反向代理配置

```powershell
notepad "C:\openresty\conf\nginx.conf"
```

找到 `http {}` 块内的 `server {}` 配置，**替换**为：

```nginx
server {
    listen       80;
    server_name  _;     # 匹配任意 IP 或域名访问

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 静态文件缓存（可选）
    location /static {
        alias C:/homework-pet/app/static;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }
}
```

> **说明**：`server_name _;` 是 Nginx/OpenResty 的通配写法，表示匹配任意 Host 头，适配公网 IP 直接访问。

### 5.4 重新加载配置

```powershell
# 先测试配置语法
C:\openresty\nginx.exe -t

# 重新加载（无需重启）
C:\openresty\nginx.exe -s reload
```

现在通过浏览器访问 `http://你的公网IP` 即可看到作业小龙页面。

---

## 6.（可选）配置 HTTPS 自签证书

> **说明**：Let's Encrypt 免费证书需要域名验证，纯 IP 无法申请。家庭/个人使用场景直接 HTTP 访问即可。如果你希望浏览器显示 🔒 图标（虽然会有安全警告），可以使用自签证书。

### 6.1 生成自签证书

```powershell
# 创建证书目录
New-Item -Path "C:\openresty\ssl" -ItemType Directory -Force

# 生成自签证书（有效期 365 天）
$cert = New-SelfSignedCertificate -DnsName "homework-pet" -CertStoreLocation "Cert:\LocalMachine\My" -NotAfter (Get-Date).AddYears(1)

# 导出证书文件
Export-Certificate -Cert $cert -FilePath "C:\openresty\ssl\server.crt"
$certPrivKey = Get-ChildItem -Path "Cert:\LocalMachine\My\$($cert.Thumbprint)"
$pwd = ConvertTo-SecureString -String "123456" -Force -AsPlainText
Export-PfxCertificate -Cert $certPrivKey -FilePath "C:\openresty\ssl\server.pfx" -Password $pwd
```

### 6.2 修改 OpenResty 配置

```powershell
notepad "C:\openresty\conf\nginx.conf"
```

将 server 块替换为同时支持 HTTP 和 HTTPS：

```nginx
server {
    listen       80;
    listen       443 ssl;
    server_name  _;

    ssl_certificate      C:/openresty/ssl/server.crt;
    ssl_certificate_key  C:/openresty/ssl/server.pfx;
    # 如果上面 pfx 导出需要密码，取消下行注释并填写密码
    # ssl_password        "123456";

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias C:/homework-pet/app/static;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }
}
```

```powershell
# 测试并重载
C:\openresty\nginx.exe -t
C:\openresty\nginx.exe -s reload
```

> ⚠️ 自签证书访问 `https://你的公网IP` 时，浏览器会显示"不安全"警告，点击"高级"→"继续访问"即可。

---

## 7. 配置 NSSM 开机自启

**NSSM**（Non-Sucking Service Manager）可以将任意程序注册为 Windows 服务，支持开机自启、崩溃自动重启。

### 7.1 下载安装

```
https://nssm.cc/download
```

下载后解压，将 `nssm.exe` 放到 `C:\nssm\` 目录，并将该目录加入系统 PATH：

```powershell
# 将 NSSM 目录加入 PATH（永久生效）
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\nssm", "Machine")

# 验证
nssm --version
```

### 7.2 注册 HomeworkPet 服务

```powershell
# 以管理员身份打开 PowerShell
nssm install HomeworkPet
```

在弹出的 GUI 窗口中填写：

| 字段 | 值 |
|------|-----|
| **Path** | `C:\homework-pet\venv\Scripts\python.exe` |
| **Arguments** | `-m uvicorn main:app --host 127.0.0.1 --port 5000` |
| **Startup directory** | `C:\homework-pet\app` |

然后切换到以下标签页进行高级配置：

**I/O 标签页**：
- **Output (stdout)**: `C:\homework-pet\logs\stdout.log`
- **Error (stderr)**: `C:\homework-pet\logs\stderr.log`

> 先创建日志目录：
> ```powershell
> New-Item -Path "C:\homework-pet\logs" -ItemType Directory -Force
> ```

**Environment 标签**：
- 添加环境变量：`PYTHONUNBUFFERED=1`（确保日志实时写入文件）

**Exit actions 标签**（配置崩溃重启）：
- **Restart action**: `Restart application`
- **Delay restart by (ms)**: `5000`

**Rotation 标签**（可选，日志轮转）：
- 勾选 `Rotate files`
- **Restrict rotation to**: `10485760`（10MB 后轮转）
- **Rotate files count**: `5`

点击 **Install service** 完成注册。

### 7.3 管理服务

```powershell
# 启动服务
nssm start HomeworkPet

# 停止服务
nssm stop HomeworkPet

# 重启服务
nssm restart HomeworkPet

# 查看服务状态
nssm status HomeworkPet

# 也可以使用 Windows 原生命令
Get-Service HomeworkPet
Restart-Service HomeworkPet
Stop-Service HomeworkPet
Start-Service HomeworkPet

# 查看服务是否设为自动启动
Get-Service HomeworkPet | Select-Object Name, StartType
```

### 7.4 设置开机自启

```powershell
sc.exe config HomeworkPet start=auto
```

### 7.5 卸载服务（如需）

```powershell
nssm stop HomeworkPet
nssm remove HomeworkPet confirm
```

### 7.6 配置 OpenResty 开机自启

同样使用 NSSM 注册 OpenResty 为服务：

```powershell
nssm install OpenResty
```

| 字段 | 值 |
|------|-----|
| **Path** | `C:\openresty\nginx.exe` |
| **Startup directory** | `C:\openresty` |
| **Arguments** | （留空） |

**I/O 标签页**：
- **Output**: `C:\openresty\logs\service-stdout.log`
- **Error**: `C:\openresty\logs\service-stderr.log`

**Exit actions 标签**：
- **Restart action**: `Restart application`
- **Delay restart by (ms)**: `5000`

```powershell
nssm start OpenResty
sc.exe config OpenResty start=auto
```

---

## 9. 配置定时任务

项目内置调度器 `/api/scheduler/run`，通过 Windows 任务计划程序定时调用。

### 9.1 方式一：PowerShell 命令创建

```powershell
# 每天 21:00 检查任务完成情况
$action = New-ScheduledTaskAction -Execute "curl.exe" -Argument "-s -X POST http://127.0.0.1:5000/api/scheduler/run"
$trigger = New-ScheduledTaskTrigger -Daily -At "21:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "HomeworkPet_Scheduler_21" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Description "作业小龙 21:00 调度"

# 每天 00:00 重置每日任务
$action2 = New-ScheduledTaskAction -Execute "curl.exe" -Argument "-s -X POST http://127.0.0.1:5000/api/scheduler/run"
$trigger2 = New-ScheduledTaskTrigger -Daily -At "00:00"
Register-ScheduledTask -TaskName "HomeworkPet_Scheduler_00" -Action $action2 -Trigger $trigger2 -Settings $settings -RunLevel Highest -Description "作业小龙 00:00 调度"
```

### 9.2 方式二：GUI 创建

1. 打开 **任务计划程序**：`Win+R` → 输入 `taskschd.msc` → 回车
2. 右侧点击 **创建基本任务**
3. 名称：`作业小龙调度器`
4. 触发器：每天，时间 `21:00`
5. 操作：启动程序
   - 程序：`C:\Windows\System32\curl.exe`
   - 参数：`-s -X POST http://127.0.0.1:5000/api/scheduler/run`
6. 完成

重复上述步骤，再创建一个 `00:00` 的任务。

### 9.3 验证定时任务

```powershell
# 查看已创建的任务
Get-ScheduledTask | Where-Object { $_.TaskName -like "*HomeworkPet*" }

# 手动运行测试
Start-ScheduledTask -TaskName "HomeworkPet_Scheduler_21"
```

---

## 10. 数据备份

### 10.1 手动备份

```powershell
# 创建备份目录
New-Item -Path "C:\homework-pet\backup" -ItemType Directory -Force

# 备份数据库
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "C:\homework-pet\app\homework_pet.db" "C:\homework-pet\backup\homework_pet_$timestamp.db"
```

### 10.2 自动备份脚本

创建备份脚本：

```powershell
notepad "C:\homework-pet\backup.ps1"
```

写入以下内容：

```powershell
# backup.ps1 - 作业小龙自动备份脚本
$backupDir = "C:\homework-pet\backup"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$keepDays = 30

# 创建备份目录
New-Item -Path $backupDir -ItemType Directory -Force | Out-Null

# 备份数据库
$dbBackup = "$backupDir\db_$timestamp.db"
Copy-Item "C:\homework-pet\app\homework_pet.db" $dbBackup

# 压缩备份
$zipFile = "$backupDir\full_$timestamp.zip"
Compress-Archive -Path "C:\homework-pet\app\homework_pet.db", "C:\homework-pet\docs" -DestinationPath $zipFile -Force

# 清理超过 30 天的备份
Get-ChildItem $backupDir -Filter "*.db" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$keepDays) } | Remove-Item -Force
Get-ChildItem $backupDir -Filter "*.zip" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$keepDays) } | Remove-Item -Force

Write-Output "[$(Get-Date)] Backup completed: $dbBackup"
```

### 10.3 配置定时备份

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File C:\homework-pet\backup.ps1 >> C:\homework-pet\backup\backup.log 2>&1"
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName "HomeworkPet_Backup" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Description "作业小龙每天凌晨 2 点自动备份"
```

### 10.4 数据恢复

```powershell
# 停止服务
nssm stop HomeworkPet

# 恢复数据库
Copy-Item "C:\homework-pet\backup\db_20260424_020000.db" "C:\homework-pet\app\homework_pet.db" -Force

# 重启服务
nssm start HomeworkPet
```

---

## 11. 防火墙配置

### 11.1 放行 HTTP 端口

以 **管理员身份** 打开 PowerShell：

```powershell
# 放行 HTTP (80)
New-NetFirewallRule -DisplayName "HTTP (80)" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow

# 放行 RDP (3389) — 如果还没放行
New-NetFirewallRule -DisplayName "RDP (3389)" -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow

# （可选）如果配置了 HTTPS 自签证书，还需放行 443
# New-NetFirewallRule -DisplayName "HTTPS (443)" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

### 11.2 查看防火墙规则

```powershell
Get-NetFirewallRule -DisplayName "*HTTP*" | Format-Table DisplayName, Enabled, Direction, Action
```

### 11.3 安全提示

- **不要**开放 5000 端口到公网。所有外部流量通过 OpenResty（端口 80）转发。
- 如果使用云服务商（如腾讯云、阿里云），还需在**云控制台安全组**中放行 80 端口（HTTPS 443 端口仅在配置自签证书时需要放行）。

---

## 12. 版本升级

### 升级流程

```powershell
# 1. 停止服务
nssm stop HomeworkPet

# 2. 备份当前数据库
$timestamp = Get-Date -Format "yyyyMMdd"
Copy-Item "C:\homework-pet\app\homework_pet.db" "C:\homework-pet\backup\homework_pet_$timestamp.db"

# 3. 拉取最新代码
Set-Location "C:\homework-pet"
git pull origin main

# 4. 更新依赖（如有变化）
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 5. 启动服务
nssm start HomeworkPet

# 6. 验证
curl.exe -s http://127.0.0.1:5000/api/pet
```

> 数据库表结构通过 `init_db()` 自动兼容升级（`ALTER TABLE ADD COLUMN`），无需手动迁移。

---

## 13. 常见问题

### Q: 访问网站显示 502 Bad Gateway

```powershell
# 检查后端服务是否运行
nssm status HomeworkPet

# 检查 OpenResty 是否运行
Get-Process nginx

# 检查端口是否被占用
netstat -ano | findstr "5000"

# 检查 OpenResty 配置语法
C:\openresty\nginx.exe -t
```

### Q: 数据库报 "database is locked"

项目已配置 WAL 模式 + busy_timeout，正常使用不会出现此问题。如果频繁出现：

```powershell
# 检查是否有多个进程同时运行
Get-Process python

# 确保只用 NSSM 管理服务，不要同时手动启动
```

### Q: 修改端口

修改 NSSM 服务参数 + OpenResty 配置：

```powershell
# 修改 NSSM 服务参数
nssm edit HomeworkPet
# 将 Arguments 中的 5000 改为目标端口

# 修改 OpenResty 配置
notepad "C:\openresty\conf\nginx.conf"
# 将 proxy_pass 中的 5000 改为目标端口

# 重启服务
C:\openresty\nginx.exe -s reload
nssm restart HomeworkPet
```

### Q: 如何修改家长密码

访问家长端 → 设置面板，输入旧密码后设置新密码。默认密码为 `1234`。

### Q: 如何查看日志

```powershell
# 应用标准输出日志
Get-Content "C:\homework-pet\logs\stdout.log" -Tail 50 -Wait

# 应用错误日志
Get-Content "C:\homework-pet\logs\stderr.log" -Tail 50 -Wait

# Nginx 错误日志
Get-Content "C:\openresty\logs\error.log" -Tail 50 -Wait

# Nginx 访问日志
Get-Content "C:\openresty\logs\access.log" -Tail 50 -Wait
```

### Q: 服务器 IP 无法访问

1. 检查云服务商**安全组**是否放行 80 端口（腾讯云/阿里云控制台）
2. 检查 Windows 防火墙是否放行（参见 [第 11 节](#11-防火墙配置)）
3. 检查 OpenResty 是否运行：`Get-Process nginx`
4. 检查 HomeworkPet 服务是否运行：`nssm status HomeworkPet`

### Q: PowerShell 报执行策略错误

```powershell
# 临时允许
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process

# 永久允许当前用户
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Q: NSSM 服务启动失败

```powershell
# 查看详细错误信息
nssm status HomeworkPet

# 检查配置
nssm edit HomeworkPet

# 手动测试启动命令
Set-Location "C:\homework-pet\app"
C:\homework-pet\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 5000
```

---

## 📋 部署检查清单

完成部署后，逐项确认：

- [ ] Python 3.8+ 已安装且加入 PATH
- [ ] 虚拟环境已创建（`C:\homework-pet\venv`）
- [ ] 依赖已安装（`pip install -r requirements.txt`）
- [ ] OpenResty 已安装且运行
- [ ] OpenResty 反向代理配置正确（`nginx -t` 测试通过）
- [ ] NSSM 服务 HomeworkPet 已注册且运行
- [ ] NSSM 服务 OpenResty 已注册且设为开机自启
- [ ] HTTP 可访问（`curl.exe http://你的公网IP`）
- [ ] 定时调度任务已创建（每天 21:00 和 00:00）
- [ ] 数据备份定时任务已创建
- [ ] Windows 防火墙已放行 80 端口
- [ ] 云服务商安全组已放行 80 端口
- [ ] 孩子端可正常访问：`http://你的公网IP/?role=kid`
- [ ] 家长端可正常访问：`http://你的公网IP/?role=parent`
- [ ] 家长密码已从默认值修改

---

部署完成！🎉 如有问题请参考 [prd.md](prd.md) 了解功能详情。
