import os
import re
from pathlib import Path

def normalize_archive_name(filename):
    """
    规格化压缩包名称。只去除压缩相关的后缀（如 .zip, .part1.rar, .7z.001），
    保留文件名中的日期或其他数字信息。
    """
    name = filename.strip()
    if not name:
        return ""
    
    # 1. 优先处理复合的分卷后缀
    name = re.sub(r'\.part\d+\.(rar|zip|7z|exe|tar)$', '', name, flags=re.I)
    name = re.sub(r'\.(7z|zip|rar|tar)\.\d{1,3}$', '', name, flags=re.I)
    name = re.sub(r'\.tar\.(gz|bz2|xz)$', '', name, flags=re.I)

    # 2. 处理单层后缀
    name = re.sub(r'\.z\d{1,3}$', '', name, flags=re.I)
    
    archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tgz', '.exe'}
    base, ext = os.path.splitext(name)
    if ext.lower() in archive_exts:
        name = base
    elif re.search(r'^\.\d{3}$', ext): 
        name = base
        
    return name.strip()

def get_names_from_source(source_path, is_archive_source=False):
    """
    从目录或文本文件中获取名称列表。
    """
    path = Path(source_path)
    if not path.exists():
        print(f"错误：路径 {source_path} 不存在。")
        return set(), {}

    names = set()
    mapping = {}

    # 如果是文本文件 (.txt)
    if path.is_file() and path.suffix.lower() == '.txt':
        raw_lines = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_lines = [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            with open(path, 'r', encoding='gbk') as f:
                raw_lines = [line.strip() for line in f if line.strip()]
        
        for item_name in raw_lines:
            if is_archive_source:
                base_name = normalize_archive_name(item_name)
                names.add(base_name)
                if base_name not in mapping:
                    mapping[base_name] = item_name
            else:
                names.add(item_name)
                mapping[item_name] = item_name
    
    # 如果是目录
    elif path.is_dir():
        for item in path.iterdir():
            if is_archive_source:
                base_name = normalize_archive_name(item.name)
                names.add(base_name)
                if base_name not in mapping:
                    mapping[base_name] = item.name
            else:
                names.add(item.name)
                mapping[item.name] = item.name
    else:
        print(f"错误：{source_path} 既不是有效的目录也不是 .txt 文件。")

    return names, mapping

def main():
    print("--- 目录/文件对比工具 (支持文件夹及 .txt 列表) ---")
    print("说明：输入可以是文件夹路径，也可以是 .txt 文件路径（一行一个名称）。")
    
    input_a = input("\n请输入【压缩包】来源 (目录或 .txt): ").strip().strip('"')
    input_b = input("请输入【文件夹】来源 (目录或 .txt): ").strip().strip('"')

    # 获取两边的名称集合
    names_a, map_a = get_names_from_source(input_a, is_archive_source=True)
    names_b, map_b = get_names_from_source(input_b, is_archive_source=False)

    # 计算差异
    only_in_a = names_a - names_b
    only_in_b = names_b - names_a

    print("\n" + "="*50)
    print(f"对比统计：")
    print(f"  - 压缩包源识别到: {len(names_a)} 组")
    print(f"  - 文件夹源识别到: {len(names_b)} 项")
    print("="*50)

    if only_in_a:
        print(f"\n[!] 【未被解压】(源中存在但目标中缺少): {len(only_in_a)}")
        for name in sorted(only_in_a):
            print(f"  - {map_a[name]}")
    else:
        print("\n[✓] 所有压缩项均已找到对应文件夹。")

    if only_in_b:
        print(f"\n[!] 【源文件已删】(目标中存在但源中缺少): {len(only_in_b)}")
        for name in sorted(only_in_b):
            print(f"  - {map_b[name]}")
    else:
        print("\n[✓] 所有文件夹在源中均有对应压缩项。")

    input("\n处理完成。按回车键退出...")

if __name__ == "__main__":
    main()
