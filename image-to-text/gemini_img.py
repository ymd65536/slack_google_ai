def _count_files(files):
    return len(files)


def count_files_msg(files):
    file_count = _count_files(files)
    return f"画像を{file_count}枚受信しました"
