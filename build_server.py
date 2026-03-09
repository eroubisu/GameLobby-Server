"""
服务器打包脚本
将服务器文件打包为 zip，用于上传到服务器替换整个目录
输出: server.zip（不含 data/ 目录，保留用户数据）
"""

import os
import zipfile

EXCLUDE_DIRS = {'__pycache__', '.git', '.github', 'data'}
EXCLUDE_EXTS = {'.pyc', '.pyo'}
EXCLUDE_FILES = {'build_server.py', 'server.zip', '.gitignore'}


def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(project_dir, 'server.zip')

    # 删除旧 zip
    if os.path.exists(output_path):
        os.remove(output_path)

    count = 0
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_dir):
            # 排除目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for filename in files:
                filepath = os.path.join(root, filename)
                _, ext = os.path.splitext(filename)

                # 排除自身和产物
                if ext in EXCLUDE_EXTS:
                    continue
                if filename in EXCLUDE_FILES:
                    continue

                arcname = os.path.relpath(filepath, project_dir)
                zf.write(filepath, arcname)
                count += 1
                print(f"  + {arcname}")

    size_kb = os.path.getsize(output_path) / 1024
    print()
    print(f"✓ 打包完成: server.zip ({size_kb:.1f} KB, {count} 个文件)")


if __name__ == "__main__":
    build()
