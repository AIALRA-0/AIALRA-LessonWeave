"""在仓库内建立独立环境，保留现有配置并启动本地网站"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--install-only',action='store_true')
    parser.add_argument('--skip-browser',action='store_true')
    parser.add_argument('--without-docling',action='store_true')
    parser.add_argument('--port',type=int,default=8960)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if sys.version_info<(3,11):raise SystemExit('请先安装 Python 3.11 或更新版本')
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
