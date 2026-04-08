import argparse
import multiprocessing
import os
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image
from tqdm import tqdm


def convert_pdf_page(args):
    """
    转换 PDF 的单页为无压缩 PNG
    """
    pdf_path, page_index, output_path = args
    try:
        # 再次打开文档（多进程安全）
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        
        # 渲染为像素图，300 DPI 保证质量
        pix = page.get_pixmap(dpi=300)
        
        # 转换为 PIL Image 并保存为无压缩格式
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(output_path, format="PNG", compress_level=0)
        
        doc.close()
        return True, None
    except Exception as e:
        return False, f"转换 {pdf_path} 第 {page_index + 1} 页失败: {str(e)}"


def get_all_pdf_tasks(root_dir):
    """
    遍历目录并准备所有待转换的任务
    """
    tasks = []
    pdf_files = list(Path(root_dir).rglob("*.pdf"))
    
    for pdf_path in pdf_files:
        try:
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
            base_name = pdf_path.stem
            
            for i in range(num_pages):
                output_name = f"{base_name}_{i + 1}.png"
                output_path = pdf_path.parent / output_name
                tasks.append((str(pdf_path), i, str(output_path)))
            
            doc.close()
        except Exception as e:
            print(f"无法读取 PDF 文件 {pdf_path}: {e}")
            
    return tasks


def main():
    parser = argparse.ArgumentParser(description="批量将 PDF 文件转换为无压缩 PNG 图像")
    parser.add_argument("dir", nargs="?", help="目标目录路径")
    args = parser.parse_args()

    root_dir = args.dir
    if not root_dir:
        root_dir = input("请输入待处理的 PDF 目录路径: ").strip().strip('"')

    if not root_dir or not os.path.isdir(root_dir):
        print(f"错误: 目录 '{root_dir}' 不存在。")
        return

    print(f"正在扫描目录: {root_dir}")
    tasks = get_all_pdf_tasks(root_dir)
    
    if not tasks:
        print("未发现 PDF 文件或文件为空。")
        return

    print(f"共发现 {len(tasks)} 个页面待转换。")

    # 多进程处理
    cpu_count = multiprocessing.cpu_count()
    num_processes = max(1, cpu_count - 1)
    print(f"使用 {num_processes} 个进程进行并行处理...")

    with multiprocessing.Pool(processes=num_processes) as pool:
        # 使用 tqdm 显示进度
        results = list(tqdm(
            pool.imap_unordered(convert_pdf_page, tasks),
            total=len(tasks),
            desc="转换进度",
            unit="页"
        ))

    # 统计结果
    success_count = sum(1 for success, _ in results if success)
    fail_count = len(results) - success_count

    print(f"\n处理完成！")
    print(f"成功: {success_count} 页")
    if fail_count > 0:
        print(f"失败: {fail_count} 页")
        for success, error in results:
            if not success:
                print(f"  - {error}")


if __name__ == "__main__":
    # Windows 多进程支持
    multiprocessing.freeze_support()
    main()
