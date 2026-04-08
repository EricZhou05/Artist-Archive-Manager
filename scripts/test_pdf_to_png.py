import fitz
import os
import subprocess
from pathlib import Path

def create_test_pdf(file_path):
    """
    创建一个简单的测试 PDF 文件
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test PDF Content", fontsize=20)
    doc.save(file_path)
    doc.close()
    print(f"创建测试 PDF: {file_path}")

def main():
    test_dir = Path("test_pdf_dir")
    test_dir.mkdir(exist_ok=True)
    
    test_pdf = test_dir / "test.pdf"
    create_test_pdf(str(test_pdf))
    
    # 运行转换脚本
    print("运行转换脚本...")
    result = subprocess.run([
        r".\venv\Scripts\python.exe", 
        "pdf_to_png.py", 
        str(test_dir)
    ], capture_output=True, text=True)
    
    print("脚本输出:")
    print(result.stdout)
    if result.stderr:
        print("错误输出:")
        print(result.stderr)
    
    # 验证生成的 PNG
    expected_png = test_dir / "test_1.png"
    if expected_png.exists():
        print(f"验证成功: 找到了生成的 PNG 文件 {expected_png}")
        # 清理
        os.remove(str(test_pdf))
        os.remove(str(expected_png))
        test_dir.rmdir()
        print("测试文件已清理。")
    else:
        print("验证失败: 未找到生成的 PNG 文件")

if __name__ == "__main__":
    main()
