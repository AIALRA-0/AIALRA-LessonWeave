#!/usr/bin/env bash
set -euo pipefail
# 在已下载的仓库中安装依赖和系统服务，账号登录继续由官方 CLI 处理
cd "$(dirname "$0")/.."
root="$(pwd)"
if [ "$(id -u)" -ne 0 ]; then echo '请使用 sudo bash deploy/install-vps.sh'; exit 1; fi
apt-get update
apt-get install -y python3 python3-venv nodejs npm docker.io
if [ "$(node -p 'Number(process.versions.node.split(".")[0])')" -lt 20 ]; then
  # 发行版自带 Node 太旧时，从官方镜像安装同一长期维护系列
  python3 - <<'PY'
import hashlib,json,platform,tarfile,tempfile,urllib.request
from pathlib import Path
rows=json.load(urllib.request.urlopen('https://nodejs.org/dist/index.json'))
version=next(r['version'] for r in rows if r['version'].startswith('v22.'))
arch={'x86_64':'x64','aarch64':'arm64'}[platform.machine()]
name='node-'+version+'-linux-'+arch+'.tar.xz'
base='https://nodejs.org/dist/'+version+'/'
with tempfile.TemporaryDirectory()as folder:
    archive=Path(folder)/name
    urllib.request.urlretrieve(base+name,archive)
    sums=urllib.request.urlopen(base+'SHASUMS256.txt').read().decode()
    expected=next(line.split()[0]for line in sums.splitlines()if line.split()[-1]==name)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise SystemExit('Node 下载不完整，请重新运行安装器')
    with tarfile.open(archive)as tar:
        for member in tar.getmembers():
            member.name='/'.join(member.name.split('/')[1:])
            if member.name:tar.extract(member,'/usr/local',filter='data')
PY
fi
systemctl enable --now docker
python3 deploy/bootstrap.py --install-only --skip-browser
.venv/bin/python -m playwright install --with-deps chromium
mkdir -p /var/lib/lessonweave /root/.codex
if [ ! -f /etc/lessonweave.env ]; then
  cp .env.example /etc/lessonweave.env
  chmod 600 /etc/lessonweave.env
fi
# 模型缓存保存在持久目录，服务无需写入其他应用目录
grep -q '^HF_HOME=' /etc/lessonweave.env || printf '\nHF_HOME=/var/lib/lessonweave/model-cache\n' >> /etc/lessonweave.env
codex_bin="$(command -v codex || true)"
if [ -z "$codex_bin" ]; then codex_bin="$root/.tools/node_modules/.bin/codex"; fi
grep -q '^LESSONWEAVE_CODEX=' /etc/lessonweave.env || printf 'LESSONWEAVE_CODEX=%s\n' "$codex_bin" >> /etc/lessonweave.env
sed "s|/srv/lessonweave/current|$root|g;s|/srv/lessonweave/venv|$root/.venv|g" deploy/lessonweave.service > /etc/systemd/system/lessonweave.service
systemctl daemon-reload
systemctl enable --now lessonweave.service
echo '服务已启动并监听 127.0.0.1:18960；请完成 Codex 登录，配置翻译凭据、所有者和现有认证反向代理'
