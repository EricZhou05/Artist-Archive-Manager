import os
import shutil

def main():
    # 获取目标目录并清理引号
    target_dir = input("请输入目标目录路径: ").strip().strip('"').strip("'")
    if not os.path.exists(target_dir):
        print(f"[ERROR] 目录不存在: {target_dir}")
        return

    # 获取搜索关键词或后缀
    search_term = input("请输入搜索关键词或文件后缀 (例如 .psd 或 keyword): ").strip().lower()

    # 确定目标基准目录
    target_dir_abs = os.path.abspath(target_dir)
    unique_base_dir = f"{target_dir_abs}_unique"

    print(f"\n[INFO] 开始扫描: {target_dir_abs}")
    print(f"[INFO] 目标目录: {unique_base_dir}\n")

    move_count = 0

    # 递归遍历目录
    for root, dirs, files in os.walk(target_dir_abs):
        # 条件：当前文件夹内没有任何子文件夹且只有一个文件
        if len(dirs) == 0 and len(files) == 1:
            filename = files[0]
            # 匹配关键词（忽略大小写）或后缀
            if search_term in filename.lower():
                src_path = os.path.join(root, filename)
                
                # 计算相对路径
                rel_path = os.path.relpath(src_path, target_dir_abs)
                dest_path = os.path.join(unique_base_dir, rel_path)
                
                # 创建目标目录结构
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                # 移动文件
                try:
                    shutil.move(src_path, dest_path)
                    print(f"[MOVE] {rel_path}")
                    move_count += 1
                except Exception as e:
                    print(f"[ERROR] 移动失败 {rel_path}: {e}")

    print(f"\n[OK] 处理完成，共移动 {move_count} 个文件。")

if __name__ == "__main__":
    main()
