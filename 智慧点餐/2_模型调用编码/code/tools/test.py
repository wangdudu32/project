
windows_path = "C:\\Users\\Admin\\Documents\\menu.txt"

print(f"不使用r: {windows_path}")
print(f"实际显示: {repr(windows_path)}")  # 显示实际内容



path_with_r = r"C:\Users\Admin\Documents\menu.txt"
print(f"使用r:   {path_with_r}")
print(f"实际显示: {repr(path_with_r)}")