"""命令行生成题目，结果保存到同一个面试记录库。"""
import argparse
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent / 'backend'))
from app.agent.tools import pdf_page_count
from app.config import get_settings
from app.interview import InterviewService
from app.llm import ModelError, create_model
from app.models import QuestionRequest
from app.storage import Storage


def main():
    parser = argparse.ArgumentParser(description='根据 PDF 创建面试，随后可在网页历史记录中作答')
    parser.add_argument('pdf_path', type=Path)
    parser.add_argument('--num', type=int, default=3, choices=range(1, 11))
    parser.add_argument('--difficulty', choices=['easy', 'medium', 'hard'], default='medium')
    parser.add_argument('--language', choices=['zh', 'en'], default='zh')
    args = parser.parse_args()
    settings = get_settings()
    source = args.pdf_path.resolve()
    try:
        if source.suffix.lower() != '.pdf' or not source.is_file():
            raise ValueError('请指定存在的 PDF 文件。')
        if source.stat().st_size > settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f'文件不能超过 {settings.max_upload_mb} MB。')
        pages = pdf_page_count(source, settings.max_pdf_pages)
        storage = Storage(settings.storage_dir)
        document_id = uuid4().hex
        path = settings.storage_dir / 'uploads' / f'{document_id}.pdf'
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, path)
        storage.add_document({'id': document_id, 'filename': source.name, 'path': str(path), 'pages': pages})
        service = InterviewService(storage, create_model(settings), settings)
        result = service.generate(QuestionRequest(document_id=document_id, num_questions=args.num,
                                                  difficulty=args.difficulty, language=args.language))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ModelError) as exc:
        parser.exit(1, f'生成失败：{exc}\n')


if __name__ == '__main__':
    main()
