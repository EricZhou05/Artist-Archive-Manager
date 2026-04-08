
import json
from collections import defaultdict

def find_duplicates_by_file():
    try:
        with open('result.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("错误：未找到 result.json 文件。")
        return
    except json.JSONDecodeError:
        print("错误：result.json 文件格式无效。")
        return

    # Use a dictionary to group messages by file signature
    files_map = defaultdict(list)
    
    messages = data.get('messages', [])

    for message in messages:
        # We are looking for forwarded messages with files
        if 'forwarded_from' not in message:
            continue

        # The user provided an example with 'file_name' and 'file_size' at the top level of the message
        # However, in standard Telegram exports, these are inside media objects.
        # Let's check both for robustness.

        file_name = message.get('file_name')
        file_size = message.get('file_size')

        # If not at top level, check inside media/document
        if file_name is None or file_size is None:
            media = message.get('media')
            if media and media.get('@type') == 'messageMediaDocument':
                document = media.get('document')
                if document:
                    # Document attributes is a list, find the file name attribute
                    for attr in document.get('attributes', []):
                        if attr.get('@type') == 'documentAttributeFilename':
                            file_name = attr.get('file_name')
                            break
                    file_size = document.get('size')

        if file_name and file_size is not None:
            # Group messages by file name and size
            unique_key = f"{file_name}_{file_size}"
            files_map[unique_key].append(message)

    # Filter for files that have been forwarded more than once
    duplicate_groups = {key: msgs for key, msgs in files_map.items() if len(msgs) > 1}

    # Write duplicate groups to a text file
    with open('duplicates.txt', 'w', encoding='utf-8') as f:
        if duplicate_groups:
            f.write("找到以下被多次转发的相同文件：\n\n")
            total_duplicates = 0
            for key, msgs in duplicate_groups.items():
                f.write(f"--- 文件 (文件名_大小: {key}) - 被转发 {len(msgs)} 次 ---\n")
                total_duplicates += len(msgs)
                for i, msg in enumerate(msgs):
                    file_name = msg.get('file_name', 'N/A')
                    file_size = msg.get('file_size', 'N/A')
                    # Fallback to media/document if not at top level
                    if file_name == 'N/A' or file_size == 'N/A':
                        media = msg.get('media')
                        if media and media.get('@type') == 'messageMediaDocument':
                            document = media.get('document')
                            if document:
                                for attr in document.get('attributes', []):
                                    if attr.get('@type') == 'documentAttributeFilename':
                                        file_name = attr.get('file_name')
                                        break
                                file_size = document.get('size')

                    from_user = msg.get('from', 'N/A')
                    forwarded_from_field = msg.get('forwarded_from')
                    forwarded_from_name = 'N/A'
                    if isinstance(forwarded_from_field, str):
                        forwarded_from_name = forwarded_from_field
                    elif isinstance(forwarded_from_field, dict):
                        forwarded_from_name = forwarded_from_field.get('name', 'N/A')


                    f.write(f"  [重复项 #{i+1}]\n")
                    f.write(f"    消息ID: {msg.get('id', 'N/A')}\n")
                    f.write(f"    日期: {msg.get('date', 'N/A')}\n")
                    f.write(f"    来源: {from_user}\n")
                    f.write(f"    转发自: {forwarded_from_name}\n")
                    f.write(f"    文件名: {file_name}\n")
                    f.write(f"    文件大小: {file_size} bytes\n")
                    f.write("\n")
                f.write("\n")
        else:
            f.write("未找到重复转发的文件。\n")

    print(f"处理完成。详情请查看 duplicates.txt。")

if __name__ == "__main__":
    find_duplicates_by_file()
