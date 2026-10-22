"""在仓库内建立独立环境，保留现有配置并启动本地网站"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv


def main():
    parser=argparse.ArgumentParser(description='安装并运行 LessonWeave 本机工作台')
    parser.add_argument('--install-only',action='store_true',help='只安装依赖，不启动工作台')
    parser.add_argument('--skip-browser',action='store_true',help='跳过 Playwright 浏览器安装')
    parser.add_argument('--without-docling',action='store_true',help='改用较轻的 PyMuPDF PDF 处理路径')
    parser.add_argument('--port',type=int,default=8960,help='LessonWeave 工作台端口，默认 8960')
    parser.add_argument('--readweave-source',help='用公开源码归档新建独立 ReadWeave 实例')
    parser.add_argument('--readweave-port',type=int,default=18961,help='ReadWeave 本机回环端口，默认 18961')
    parser.add_argument('--dry-run',action='store_true',help='只检查并显示计划，不安装依赖、不启动服务')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if sys.version_info<(3,11):raise SystemExit('请先安装 Python 3.11 或更新版本')
    if args.readweave_port<1024 or args.readweave_port>65535:parser.error('--readweave-port 必须在 1024 到 65535 之间')
    if args.dry_run:
        print('dry-run：不会创建虚拟环境、安装依赖、登录 Codex 或启动 LessonWeave')
        if args.readweave_source:
            subprocess.run([sys.executable,str(root/'deploy/readweave_bootstrap.py'),'--source',args.readweave_source,'--port',str(args.readweave_port),'--env-file',str(root/'.env'),'--dry-run'],check=True)
        else:
            print('本机工作台地址为 http://127.0.0.1:'+str(args.port)+'/workspace')
        return
    target=root/'.venv'
    if not target.is_dir():venv.EnvBuilder(with_pip=True).create(target)
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not args.without_docling and platform_cpu():
        subprocess.run([str(python),'-m','pip','install','torch==2.8.0','torchvision==0.23.0','--index-url','https://download.pytorch.org/whl/cpu'],check=True)
    subprocess.run([str(python),'-m','pip','install','-e',str(root)+('' if args.without_docling else '[pdf]')],check=True)
    if not args.skip_browser:subprocess.run([str(python),'-m','playwright','install','chromium'],check=True)
    executable=os.environ.get('LESSONWEAVE_CODEX') or shutil.which('codex')
    if not executable:
        npm=shutil.which('npm')
        if not npm:raise SystemExit('请先安装 Node.js 20 或更新版本，再运行本脚本')
        subprocess.run([npm,'install','--prefix',str(root/'.tools'),'@openai/codex'],check=True,shell=os.name=='nt')
        executable=str(root/'.tools/node_modules/.bin'/('codex.cmd' if os.name=='nt' else 'codex'))
    config=root/'.env'
    if config.is_file():
        for line in config.read_text('utf8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key,value=line.split('=',1);os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
    os.environ.setdefault('LESSONWEAVE_CODEX',executable)
    os.environ.setdefault('LESSONWEAVE_DATA',str(Path.home()/'.lessonweave'))
    os.environ.setdefault('LESSONWEAVE_PDF_ENGINE','docling' if not args.without_docling else 'pymupdf')
    readweave_keys = (
        'LESSONWEAVE_READWEAVE_URL', 'LESSONWEAVE_READWEAVE_TOKEN',
        'LESSONWEAVE_TRILIUM_URL', 'LESSONWEAVE_TRILIUM_TOKEN',
    )
    if args.readweave_source or any(os.environ.get(key, '').strip() for key in readweave_keys):
        command = [sys.executable, str(root/'deploy/readweave_bootstrap.py'),
                   '--port', str(args.readweave_port), '--env-file', str(config)]
        if args.readweave_source:
            command.extend(['--source', args.readweave_source])
        subprocess.run(command, check=True)
        # Read back credentials and directory IDs that the helper just saved before
        # starting the web process in this same installer invocation.
        managed_keys = (*readweave_keys, 'LESSONWEAVE_READWEAVE_BRIDGE',
                        'LESSONWEAVE_TRILIUM_ROOT', 'LESSONWEAVE_TRILIUM_TRASH')
        for line in config.read_text('utf8').splitlines() if config.is_file() else []:
            if '=' not in line or line.lstrip().startswith('#'):
                continue
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key in managed_keys:
                os.environ[key] = value
    if args.install_only:
        print('安装完成；网站配置和 Codex 登录保留在仓库外或未跟踪的 .env 中')
        return
    if subprocess.run([executable,'login','status'],shell=os.name=='nt').returncode:
        subprocess.run([executable,'login','--device-auth'],check=True,shell=os.name=='nt')
    print('打开 http://127.0.0.1:'+str(args.port)+'/workspace',flush=True)
    subprocess.run([str(python),'-B','-m','lessonweave','serve','--port',str(args.port)],cwd=root,check=True)


def platform_cpu():
    import platform
    return platform.system() in {'Windows','Linux'} and platform.machine().lower() in {'amd64','x86_64'}


if __name__=='__main__':main()
