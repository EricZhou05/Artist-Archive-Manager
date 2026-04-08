import re
from datetime import datetime

def format_date(date_str):
    """将各种日期格式转换为 YYYY-MM-DD"""
    if not date_str:
        return "Unknown"
    # 替换常见的符号（增加对下划线的支持）
    clean_date = date_str.replace(".", "-").replace("/", "-").replace("_", "-").strip()
    # 尝试匹配 YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", clean_date)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return "Unknown"

def smart_recognize(raw_input):
    """模式一：智能识别"""
    # 预处理：将中文括号、全角标点和全角空格转换为英文/半角格式
    raw_input = raw_input.replace('（', '(').replace('）', ')').replace('【', '[').replace('】', ']')
    raw_input = raw_input.replace('［', '[').replace('］', ']')
    raw_input = raw_input.replace('　', ' ') # 全角空格
    
    # 1. 提取平台 []
    platforms_raw = re.findall(r"\[(.*?)\]", raw_input)
    platforms = []
    known_platforms = ["PIXIV", "FANBOX", "DISCORD", "X", "TWITTER", "BOOTH", "PATREON", "CI-EN"]
    
    potential_dates = []
    
    for p in platforms_raw:
        p_upper = p.upper()
        # 排除包含日期特征的项（增加对下划线的支持）
        if re.search(r"\d{4}[.\-/_]\d{1,2}", p):
            potential_dates.append(p)
            continue
        # 排除包含 'page' 的项（如 [57 pages]）
        if "PAGE" in p_upper:
            continue
        
        # 处理 Pixiv&Discord 这种合并情况
        parts = re.split(r"[&/]", p)
        for part in parts:
            platforms.append(part.strip())

    # 2. 提取 ID ()
    # 优先找纯数字的长字符串
    ids = re.findall(r"\((\d{5,})\)", raw_input)
    if not ids:
        # 退而求其次找括号里的数字
        ids = re.findall(r"\((\d+)\)", raw_input)
    
    artist_id = ids[0] if ids else "Unknown"

    # 3. 提取时间范围
    # 查找类似 (2024.01.02 - 2025.05.19) 或 [2023.10.22]
    # 正则表达式中增加了对下划线 _ 的匹配支持
    date_range_match = re.search(r"\(?(\d{4}[.\-/_]\d{1,2}[.\-/_]\d{1,2})\s*[-~至]\s*(\d{4}[.\-/_]\d{1,2}[.\-/_]\d{1,2})\)?", raw_input)
    
    start_date = "Unknown"
    end_date = "Unknown"
    
    if date_range_match:
        start_date = format_date(date_range_match.group(1))
        end_date = format_date(date_range_match.group(2))
    else:
        # 尝试查找单个日期（同样增加下划线支持）
        single_dates = re.findall(r"(\d{4}[.\-/_]\d{1,2}[.\-/_]\d{1,2})", raw_input)
        if len(single_dates) == 1:
            # 模式一：只识别到一个日期，格式化为 (Unknown - 日期)
            end_date = format_date(single_dates[0])
        elif len(single_dates) >= 2:
            start_date = format_date(single_dates[0])
            end_date = format_date(single_dates[1])

    # 4. 提取作者名
    # 移除已识别的所有括号内容
    clean_name = raw_input
    # 移除所有 [] 和 ()
    clean_name = re.sub(r"\[.*?\]", " ", clean_name)
    clean_name = re.sub(r"\(.*?\)", " ", clean_name)
    # 移除剩余的日期和ID
    if artist_id != "Unknown":
        clean_name = clean_name.replace(artist_id, " ")
    
    # 清理多余空格和特殊字符
    clean_name = re.sub(r"[\(\)\[\]]", "", clean_name)
    clean_name = " ".join(clean_name.split()).strip()
    
    if not clean_name:
        clean_name = "Unknown"

    # 组合结果
    platform_str = " ".join([f"[{p}]" for p in platforms]) if platforms else "[Unknown]"
    # 无论日期是否存在，都保持 (Start - End) 格式
    date_str = f"({start_date} - {end_date})"
    id_str = f"({artist_id})"
    
    final_name = f"{platform_str} {clean_name} {id_str} {date_str}"
    return final_name

def sequential_prompt():
    """模式二：依次询问"""
    print("\n--- 模式二：依次询问命名 ---")
    
    # 1. 平台
    print("选择图集平台 (可输入多个，用空格隔开):")
    print("1. Pixiv  2. Fanbox  3. Discord  4. X  5. Unknown")
    choice = input("请输入选项编号或直接输入名称: ").strip()
    
    mapping = {"1": "Pixiv", "2": "Fanbox", "3": "Discord", "4": "X", "5": "Unknown"}
    selected_platforms = []
    for part in choice.split():
        if part in mapping:
            if mapping[part] != "Unknown":
                selected_platforms.append(mapping[part])
        else:
            selected_platforms.append(part)
    
    if not selected_platforms:
        platform_str = "[Unknown]"
    else:
        # 最多叠加两个
        platform_str = " ".join([f"[{p}]" for p in selected_platforms[:2]])

    # 2. 用户名
    artist_name = input("请输入作者名称 (留空为 Unknown): ").strip() or "Unknown"
    # 规范化可能的中文括号
    artist_name = artist_name.replace('（', '(').replace('）', ')').replace('【', '[').replace('】', ']')

    # 3. ID
    artist_id = input("请输入P站/作者ID (留空为 Unknown): ").strip() or "Unknown"

    # 4. 时间
    start_t = input("请输入起始时间 (例如 2024.1.1, 留空为 Unknown): ").strip()
    end_t = input("请输入结束时间 (例如 2024.12.31, 留空为 Unknown): ").strip()
    
    start_date = format_date(start_t)
    end_date = format_date(end_t)
    
    # 模式二：始终保持 (Start - End) 格式
    date_str = f"({start_date} - {end_date})"
    id_str = f"({artist_id})"
    
    final_name = f"{platform_str} {artist_name} {id_str} {date_str}"
    return final_name

def main():
    while True:
        print("\n=== 智能文件名生成脚本 ===")
        print("标准格式: [来源] 作者名 (ID) (YYYY-MM-DD - YYYY-MM-DD)")
        print("1. 模式一：智能识别（粘贴乱序文件名）")
        print("2. 模式二：依次询问（手动输入）")
        print("提示: 也可直接粘贴文件名进行智能识别")
        print("q. 退出")
        
        mode = input("\n请选择模式: ").strip()
        
        if not mode:
            continue

        if mode.lower() == 'q':
            break
        elif mode == '1':
            raw_input = input("请粘贴原始文件名: ").strip()
            if raw_input:
                result = smart_recognize(raw_input)
                print("\n--- 识别结果 ---")
                print(result)
                print("----------------")
            else:
                print("输入不能为空！")
        elif mode == '2':
            result = sequential_prompt()
            print("\n--- 生成结果 ---")
            print(result)
            print("----------------")
        else:
            # 如果输入不是 1, 2 或 q，则将其视为需要识别的内容
            result = smart_recognize(mode)
            print("\n--- 智能识别结果 ---")
            print(result)
            print("----------------")

if __name__ == "__main__":
    main()
