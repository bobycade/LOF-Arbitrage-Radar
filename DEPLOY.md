# 服务器采购指引

## 推荐方案：腾讯云轻量应用服务器

### 为什么选腾讯云？

1. **访问速度快**：服务器在国内，访问东方财富、天天基金等数据接口速度快且稳定
2. **价格实惠**：新用户首年优惠大，约¥50-80/月
3. **运维简单**：提供完善的控制台和一键安装脚本
4. **稳定可靠**：腾讯云基础设施成熟，故障率低

### 购买步骤

#### 1. 注册/登录腾讯云

- 访问：https://cloud.tencent.com/
- 点击右上角"注册"或"登录"
- 推荐使用微信扫码登录，方便快捷

#### 2. 进入轻量应用服务器页面

- 登录后，搜索"轻量应用服务器"
- 或直接访问：https://cloud.tencent.com/product/lighthouse

#### 3. 选择配置

**推荐配置：**

| 配置项 | 推荐选择 | 说明 |
|--------|---------|------|
| **地域** | 北京/上海/广州 | 选择离你最近的 |
| **可用区** | 随机选择 | 都可以 |
| **镜像** | Ubuntu 20.04 LTS | 社区支持好 |
| **套餐** | 2核2G | 性能足够，约¥50-80/月 |
| **流量包** | 选择包含500GB/月 | 这个项目流量需求不大 |

#### 4. 设置服务器

- **实例名称**：LOF套利雷达（随便填）
- **购买时长**：首年推荐1年（有优惠）
- **数量**：1台

#### 5. 设置登录方式

推荐使用**密码登录**：
- 设置root密码（务必记住！）
- 至少8位，包含大小写字母+数字

#### 6. 提交订单

- 检查配置无误后，点击"立即购买"
- 支付费用
- 等待服务器创建（约1-5分钟）

### 购买后操作

#### 1. 获取服务器IP地址

- 登录腾讯云控制台
- 进入"轻量应用服务器"
- 查看服务器实例的**公网IP**（如：1.2.3.4）

#### 2. 测试连接

**Windows用户：**
```powershell
# 打开PowerShell，替换YOUR_IP
ssh root@YOUR_IP
```

**Mac/Linux用户：**
```bash
ssh root@YOUR_IP
```

输入密码（密码不会显示），连接成功后看到欢迎信息。

#### 3. 上传项目文件

**方式1：Git（推荐）**
```bash
# 将项目上传到GitHub后
cd /root
git clone YOUR_REPO_URL lof_arbitrage
cd lof_arbitrage
```

**方式2：SCP（Windows本地）**
```powershell
# 在本地PowerShell执行
scp -r "C:\Users\CC\WorkBuddy\Claw\lof_arbitrage" root@YOUR_IP:/root/
```

#### 4. 运行一键部署脚本

```bash
cd /root/lof_arbitrage
chmod +x quickstart.sh
bash quickstart.sh
```

#### 5. 配置环境变量

```bash
nano .env
```

编辑以下关键配置：

```bash
WECHAT_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY
SMTP_PASSWORD=your_smtp_auth_code
```

#### 6. 重启应用

```bash
supervisorctl restart lof_arbitrage
```

#### 7. 访问网页

浏览器访问：`http://YOUR_IP:5000`

### 费用说明

| 项目 | 价格 |
|------|------|
| 轻量应用服务器（2核2G） | 约¥50-80/月 |
| 流量包 | 已包含 |
| 其他费用 | 无 |

**年费预估**：约¥600-1000/年

### 备选方案

#### 阿里云

- 类似配置，价格相近
- 访问：https://www.aliyun.com/product/swas
- 适合已有阿里云账号的用户

#### 华为云

- 略便宜约¥10/月
- 访问：https://www.huaweicloud.com/product/lts.html
- 生态不如腾讯云

### 不推荐：国外云服务器

**不推荐使用：**
- Vultr、DigitalOcean、RackNerd等国外云

**原因：**
1. 访问国内数据接口（东方财富、天天基金）容易被限速或屏蔽
2. 网络延迟高，影响数据实时性
3. 可能违反数据接口的使用条款

### 注意事项

1. **密码安全**：root密码请妥善保管
2. **防火墙**：记得在腾讯云控制台开放5000端口
3. **定期备份**：定期备份数据库文件`lof_data.db`
4. **监控费用**：注意流量包使用情况，避免超额
5. **及时续费**：服务器到期后数据会被清除

### 购买链接

**腾讯云轻量服务器：**
https://cloud.tencent.com/product/lighthouse

**阿里云轻量应用服务器：**
https://www.aliyun.com/product/swas

---

有问题？查看完整文档：[README.md](README.md)
