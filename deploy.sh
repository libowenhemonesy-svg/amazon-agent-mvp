#!/bin/bash
# Amazon Agent 部署脚本
# 适用于腾讯云轻量服务器 (Ubuntu/Debian)

set -e

echo "=========================================="
echo "  Amazon Agent 部署脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}请使用 root 用户运行此脚本${NC}"
  echo "运行: sudo bash deploy.sh"
  exit 1
fi

# 获取服务器 IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
echo -e "${GREEN}服务器 IP: ${SERVER_IP}${NC}"

# 1. 更新系统
echo -e "\n${YELLOW}[1/6] 更新系统...${NC}"
apt update -y
apt upgrade -y

# 2. 安装依赖
echo -e "\n${YELLOW}[2/6] 安装系统依赖...${NC}"
apt install -y python3 python3-pip python3-venv git curl

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}Python 版本: ${PYTHON_VERSION}${NC}"

# 3. 创建项目目录
echo -e "\n${YELLOW}[3/6] 创建项目目录...${NC}"
PROJECT_DIR="/opt/amazon-agent"
mkdir -p $PROJECT_DIR

# 4. 克隆代码
echo -e "\n${YELLOW}[4/6] 克隆代码...${NC}"
if [ -d "$PROJECT_DIR/.git" ]; then
  echo "项目已存在，拉取最新代码..."
  cd $PROJECT_DIR
  git pull
else
  echo "克隆新项目..."
  git clone https://github.com/libowenhemonesy-svg/amazon-agent-mvp.git $PROJECT_DIR
  cd $PROJECT_DIR
fi

# 5. 创建虚拟环境并安装依赖
echo -e "\n${YELLOW}[5/6] 安装 Python 依赖...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. 创建环境配置文件
echo -e "\n${YELLOW}[6/6] 配置环境变量...${NC}"
if [ ! -f .env ]; then
  cp .env.example .env
  echo -e "${YELLOW}请编辑 /opt/amazon-agent/.env 文件配置 API 密钥${NC}"
fi

# 创建 systemd 服务
echo -e "\n${YELLOW}创建系统服务...${NC}"
cat > /etc/systemd/system/amazon-agent.service << EOF
[Unit]
Description=Amazon Agent MVP
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
ExecStart=$PROJECT_DIR/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重载 systemd 并启动服务
systemctl daemon-reload
systemctl enable amazon-agent
systemctl restart amazon-agent

# 等待服务启动
sleep 3

# 检查服务状态
if systemctl is-active --quiet amazon-agent; then
  echo -e "\n${GREEN}==========================================${NC}"
  echo -e "${GREEN}  部署成功！${NC}"
  echo -e "${GREEN}==========================================${NC}"
  echo -e "\n访问地址: http://${SERVER_IP}:8010"
  echo -e "\n常用命令:"
  echo -e "  查看状态: ${YELLOW}systemctl status amazon-agent${NC}"
  echo -e "  查看日志: ${YELLOW}journalctl -u amazon-agent -f${NC}"
  echo -e "  重启服务: ${YELLOW}systemctl restart amazon-agent${NC}"
  echo -e "  停止服务: ${YELLOW}systemctl stop amazon-agent${NC}"
  echo -e "\n配置文件: ${YELLOW}/opt/amazon-agent/.env${NC}"
else
  echo -e "\n${RED}==========================================${NC}"
  echo -e "${RED}  部署失败，请查看日志${NC}"
  echo -e "${RED}==========================================${NC}"
  echo -e "查看日志: journalctl -u amazon-agent -n 50"
fi
