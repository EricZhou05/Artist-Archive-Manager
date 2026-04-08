import os
import re
import logging
import threading
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        def __init__(self, total, **kwargs): self.total = total
        def update(self, n=1): pass
        def close(self): pass
        def set_postfix(self, **kwargs): pass

# 配置 Bandizip 路径 (使用 bz.exe 实现全静默后台解压)
BANDIZIP_EXE = r"D:\Program Files\Bandizip\bz.exe"
stats_lock = threading.Lock()

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler("decryption_log.txt", encoding='utf-8', mode='a')]
    )

def get_passwords_from_txt(txt_path):
    passwords = []
    if not os.path.exists(txt_path): return passwords
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 匹配 pass : xxx 格式
                match = re.search(r'pass\s*:\s*(\S+)', line, re.IGNORECASE)
                if match: passwords.append(match.group(1))
    except Exception as e:
        logging.error(f"读取密码文件 {txt_path} 失败: {e}")
    return list(set(passwords))

def get_all_possible_passwords(zip_path):
    zip_path = Path(zip_path)
    # 提取前缀，去除结尾的数字和空格
    prefix = re.sub(r'\s+\d+$', '', zip_path.stem)
    passwords = []
    try:
        for txt_file in zip_path.parent.glob(f"{prefix}*.txt"):
            passwords.extend(get_passwords_from_txt(str(txt_file)))
    except Exception: pass
    return list(set(passwords))

def _attempt_extraction(zip_path, target_dir, password, code_page=None):
    """单次解压尝试"""
    try:
        cmd = [BANDIZIP_EXE, "x"]
        if password:
            cmd.append(f"-p:{password}")
        if code_page:
            cmd.append(f"-cp:{code_page}")
        cmd.extend([f"-o:{target_dir}", "-y", str(zip_path)])
        
        # creationflags=subprocess.CREATE_NO_WINDOW 隐藏控制台弹窗
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore', creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0, result.stderr or result.stdout or "解压失败"
    except Exception as e:
        return False, str(e)

def decrypt_with_bandizip(zip_path, universal_pwd=None, code_page=None):
    zip_path = Path(zip_path)
    target_dir = zip_path.parent / zip_path.stem
    
    # 1. 首先尝试无密码解压
    success, err = _attempt_extraction(zip_path, target_dir, "", code_page)
    if success:
        logging.info(f"成功: {zip_path.name} (无密码)")
        return "SUCCESS", str(zip_path), ""

    # 2. 如果失败且未提供通用密码，则检查同目录密码文件
    if not universal_pwd:
        local_passwords = get_all_possible_passwords(zip_path)
        for pwd in local_passwords:
            success, err = _attempt_extraction(zip_path, target_dir, pwd, code_page)
            if success:
                logging.info(f"成功: {zip_path.name} (本地密码: {pwd})")
                return "SUCCESS", str(zip_path), ""
    else:
        # 3. 如果提供了通用密码，则直接尝试
        success, err = _attempt_extraction(zip_path, target_dir, universal_pwd, code_page)
        if success:
            logging.info(f"成功: {zip_path.name} (通用密码)")
            return "SUCCESS", str(zip_path), ""

    return "FAIL", str(zip_path), err

def process_folder(root_folder, code_page=None):
    setup_logging()
    if not os.path.exists(BANDIZIP_EXE):
        print(f"错误: 找不到 Bandizip 可执行文件: {BANDIZIP_EXE}")
        return

    zip_files = list(Path(root_folder).rglob("*.zip"))
    if not zip_files:
        print("未找到任何 ZIP 文件。")
        return

    total = len(zip_files)
    max_workers = min(os.cpu_count() or 4, 12) 
    
    mode_str = " (强制日语编码)" if code_page == "932" else ""
    print(f"开始并行解压{mode_str}: {total} 个文件 (线程: {max_workers})")
    
    stats = {"success": 0, "failed": 0}
    first_pass_failed = []
    pbar = tqdm(total=total, desc="整体进度")

    # 第一轮：尝试无密码和本地密码
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(decrypt_with_bandizip, z, None, code_page): z for z in zip_files}
        for future in as_completed(futures):
            status, path_str, err = future.result()
            with stats_lock:
                if status == "SUCCESS":
                    stats["success"] += 1
                else:
                    first_pass_failed.append(path_str)
                pbar.update(1)
                pbar.set_postfix(成功=stats["success"], 待定=len(first_pass_failed))
    pbar.close()

    # 如果有失败的，询问通用密码并全局应用
    if first_pass_failed:
        print(f"\n[!] 第一轮完成，共有 {len(first_pass_failed)} 个文件解压失败。")
        universal_pwd = input("请输入通用密码以重试（直接回车跳过）: ").strip()
        
        if universal_pwd:
            print(f"正在使用通用密码重试 {len(first_pass_failed)} 个文件...")
            retry_pbar = tqdm(total=len(first_pass_failed), desc="重试进度")
            still_failed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                retry_futures = {executor.submit(decrypt_with_bandizip, Path(f), universal_pwd, code_page): f for f in first_pass_failed}
                for future in as_completed(retry_futures):
                    status, path_str, err = future.result()
                    if status == "SUCCESS":
                        with stats_lock:
                            stats["success"] += 1
                    else:
                        still_failed_count += 1
                        logging.error(f"最终失败: {path_str} - {err}")
                    retry_pbar.update(1)
            retry_pbar.close()
            stats["failed"] = still_failed_count
        else:
            stats["failed"] = len(first_pass_failed)
            for f in first_pass_failed:
                logging.error(f"失败 (未提供通用密码): {f}")
    else:
        stats["failed"] = 0

    print(f"\n任务完成！\n成功: {stats['success']}\n失败: {stats['failed']}")
    print(f"详细日志: {os.path.abspath('decryption_log.txt')}")

def verify_extractions(root_folder):
    """检验模式：检查是否有压缩包漏解压（没有同名文件夹）"""
    root_path = Path(root_folder)
    zip_files = list(root_path.rglob("*.zip"))
    
    if not zip_files:
        print("未找到任何 ZIP 文件。")
        return

    print(f"正在检验目录: {root_folder}")
    missing = []
    for zip_path in zip_files:
        target_dir = zip_path.parent / zip_path.stem
        if not target_dir.is_dir():
            missing.append(zip_path)
    
    if missing:
        print(f"\n[!] 发现 {len(missing)} 个压缩包可能漏解压（未找到同名文件夹）:")
        for m in missing:
            print(f"  - {m}")
    else:
        print("\n[OK] 所有压缩包均已找到对应的同名文件夹，未发现明显漏解压。")

if __name__ == "__main__":
    import sys
    print("="*40)
    print("Bandizip 批量自动解压工具")
    print("1. 默认解压模式 (自动识别编码)")
    print("2. 强制日语编码模式 (解决日文乱码, CP932)")
    print("3. 检验模式 (检查是否有漏解压)")
    print("="*40)
    
    choice = input("请选择模式 [1/2/3] (默认1): ").strip() or "1"
    
    if choice == "3":
        path = input("【检验模式】请输入要检查的文件夹路径: ").strip().strip('"')
        if os.path.isdir(path):
            verify_extractions(path)
        else:
            print(f"路径无效: {path}")
    elif choice in ["1", "2"]:
        path = input(f"【{'强制日语' if choice=='2' else '默认'}模式】请输入文件夹路径: ").strip().strip('"')
        if os.path.isdir(path):
            cp = "932" if choice == "2" else None
            process_folder(path, code_page=cp)
        else:
            print(f"路径无效: {path}")
    else:
        print("无效选择。")
