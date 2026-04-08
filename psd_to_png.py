import os
import sys
import argparse
from pathlib import Path
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor
from psd_tools import PSDImage
from tqdm import tqdm

def convert_psd_to_png(psd_path):
    """
    将单个 PSD 文件转换为 PNG。
    合并可见图层，忽略隐藏图层，并以无压缩格式保存。
    """
    try:
        psd_path = Path(psd_path)
        png_path = psd_path.with_suffix('.png')
        
        # 加载 PSD 文件
        psd = PSDImage.open(psd_path)
        
        # 合并所有可见图层 (自动忽略隐藏图层)
        image = psd.composite()
        
        # 保存为 PNG，设置 compress_level=0 实现无压缩
        image.save(png_path, format='PNG', compress_level=0)
        return True, psd_path
    except Exception as e:
        return False, f"处理失败 {psd_path}: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description="批量将 PSD 转换为 PNG（合并可见图层）。")
    parser.add_argument("input_dir", nargs="?", help="要搜索 PSD 文件的根目录。")
    args = parser.parse_args()

    # 获取输入目录
    input_dir = args.input_dir
    if not input_dir:
        input_dir = input("请输入需要处理的根目录: ").strip()
    
    # 处理可能的引号包裹 (单引号或双引号)
    if input_dir:
        input_dir = input_dir.strip().strip("'").strip('"')

    if not input_dir:
        print("错误: 未提供目录。")
        sys.exit(1)
    
    root = Path(input_dir)
    if not root.is_dir():
        print(f"错误: 目录不存在 - {root}")
        sys.exit(1)

    # 递归查找所有 PSD 文件
    print(f"正在扫描目录: {root} ...")
    psd_files = list(root.rglob("*.psd"))
    
    if not psd_files:
        print("未找到任何 PSD 文件。")
        return

    total_files = len(psd_files)
    # 使用 CPU 核心数 - 1，至少保留 1 核
    cores = max(1, cpu_count() - 1)
    
    print(f"找到 {total_files} 个 PSD 文件。")
    print(f"使用并行进程数: {cores}")

    # 使用进程池进行并行处理
    errors = []
    with ProcessPoolExecutor(max_workers=cores) as executor:
        # 使用 tqdm 显示进度条
        results = list(tqdm(executor.map(convert_psd_to_png, psd_files), total=total_files, desc="转换进度"))

    # 统计错误
    for success, message in results:
        if not success:
            errors.append(message)

    if errors:
        print("\n部分文件处理出错:")
        for err in errors:
            print(err)
    
    print(f"\n任务完成。总计: {total_files}, 成功: {total_files - len(errors)}, 失败: {len(errors)}")

if __name__ == "__main__":
    main()
