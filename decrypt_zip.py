import os
import re
import shutil
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
        def write(self, msg): print(msg)

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
                match = re.search(r'pass\s*:\s*(\S+)', line, re.IGNORECASE)
                if match: passwords.append(match.group(1))
    except Exception as e:
        logging.error(f"读取密码文件 {txt_path} 失败: {e}")
    return list(set(passwords))

def get_all_possible_passwords(zip_path):
    zip_path = Path(zip_path)
    prefix = re.sub(r'\s+\d+$', '', zip_path.stem)
    passwords = []
    try:
        for txt_file in zip_path.parent.glob(f"{prefix}*.txt"):
            passwords.extend(get_passwords_from_txt(str(txt_file)))
    except Exception: pass
    return list(set(passwords))

def _clean_target_dir(target_dir):
    """清除尝试失败留下的残余文件夹，防止下一次试错被卡死或判定错误"""
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir, ignore_errors=True)
        except Exception:
            pass

def _attempt_extraction(zip_path, target_dir, password, code_page=None):
    """
    单次解压尝试
    -y -aoa: 强制静默且自动覆盖所有同名文件，防止弹提示卡死
    """
    try:
        cmd = [BANDIZIP_EXE, "x", "-y", "-aoa"]
        if password:
            cmd.append(f"-p:{password}")
        if code_page:
            cmd.append(f"-cp:{code_page}")
        cmd.extend([f"-o:{target_dir}", str(zip_path)])
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=180  # 增加 3 分钟超时断路器，防止意外死锁
        )
        
        success = (result.returncode == 0)
        
        # 如果失败，一定要把失败时产生的垃圾文件删掉！
        if not success:
            _clean_target_dir(target_dir)
            
        return success, "密码错误或损坏"
    except subprocess.TimeoutExpired:
        _clean_target_dir(target_dir)
        return False, "解压超时"
    except Exception as e:
        _clean_target_dir(target_dir)
        return False, str(e)

def decrypt_with_bandizip(zip_path, password_list=None, code_page=None):
    zip_path = Path(zip_path)
    target_dir = zip_path.parent / zip_path.stem
    
    # 1. 第一轮模式：尝试无密码以及同目录 txt 自动识别密码
    if password_list is None:
        success, err = _attempt_extraction(zip_path, target_dir, "", code_page)
        if success:
            msg = f"[成功] {zip_path.name} | 密码: (无密码)"
            logging.info(msg)
            return "SUCCESS", str(zip_path), "", msg

        local_passwords = get_all_possible_passwords(zip_path)
        for pwd in local_passwords:
            success, err = _attempt_extraction(zip_path, target_dir, pwd, code_page)
            if success:
                msg = f"[成功] {zip_path.name} | 密码: {pwd} (源自同名txt)"
                logging.info(msg)
                return "SUCCESS", str(zip_path), pwd, msg
        
        return "FAIL", str(zip_path), err, ""

    # 2. 第二轮重试模式：使用用户密码列表匹配
    last_err = "所有指定密码均匹配失败"
    for pwd in password_list:
        success, err = _attempt_extraction(zip_path, target_dir, pwd, code_page)
        if success:
            msg = f"[匹配成功] {zip_path.name}  ===>  密码: {pwd}"
            logging.info(msg)
            return "SUCCESS", str(zip_path), pwd, msg
        last_err = err

    return "FAIL", str(zip_path), last_err, ""

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
    cpu_count = os.cpu_count() or 4
    max_workers = min(cpu_count, 8) 
    
    mode_str = " (强制日语编码)" if code_page == "932" else ""
    print(f"开始并行解压{mode_str}: {total} 个文件 (线程: {max_workers})")
    
    stats = {"success": 0, "failed": 0}
    first_pass_failed = []
    pbar = tqdm(total=total, desc="整体进度")

    # 第一轮：无密码 / 同名 txt 匹配
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(decrypt_with_bandizip, z, None, code_page): z for z in zip_files}
        for future in as_completed(futures):
            status, path_str, pwd, log_msg = future.result()
            with stats_lock:
                if status == "SUCCESS":
                    stats["success"] += 1
                    tqdm.write(log_msg)
                else:
                    first_pass_failed.append(path_str)
                pbar.update(1)
                pbar.set_postfix(成功=stats["success"], 待定=len(first_pass_failed))
    pbar.close()

    # 第二轮：密码列表爆破匹配
    if first_pass_failed:
        print(f"\n[!] 第一轮完成，共有 {len(first_pass_failed)} 个文件解压失败。")
        print("请输入用于重试的密码列表（一行一个，连续两次回车或直接按 ENTER 结束）：")
        
        user_passwords = []
        while True:
            try:
                line = input()
                if not line.strip():
                    break
                user_passwords.append(line.strip())
            except EOFError:
                break
        
        user_passwords = list(dict.fromkeys(user_passwords))
        
        if user_passwords:
            print(f"\n正在使用包含 {len(user_passwords)} 个密码的列表匹配重试 {len(first_pass_failed)} 个文件...")
            retry_pbar = tqdm(total=len(first_pass_failed), desc="重试进度")
            still_failed_count = 0
            
            # 多密码解压降低并发线程，防止磁盘 I/O 阻塞
            retry_workers = max(1, min(cpu_count // 2, 4))
            
            with ThreadPoolExecutor(max_workers=retry_workers) as executor:
                retry_futures = {
                    executor.submit(decrypt_with_bandizip, Path(f), user_passwords, code_page): f 
                    for f in first_pass_failed
                }
                for future in as_completed(retry_futures):
                    status, path_str, pwd, log_msg = future.result()
                    if status == "SUCCESS":
                        with stats_lock:
                            stats["success"] += 1
                        tqdm.write(log_msg)
                    else:
                        still_failed_count += 1
                        tqdm.write(f"[匹配失败] {Path(path_str).name} (列表中 39 个密码全都不对)")
                        logging.error(f"最终失败: {path_str} - {pwd}")
                    retry_pbar.update(1)
            retry_pbar.close()
            stats["failed"] = still_failed_count
        else:
            stats["failed"] = len(first_pass_failed)
            for f in first_pass_failed:
                logging.error(f"失败 (未提供重试密码): {f}")
    else:
        stats["failed"] = 0

    print(f"\n任务完成！\n成功: {stats['success']}\n失败: {stats['failed']}")
    print(f"详细日志已保存至: {os.path.abspath('decryption_log.txt')}")

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