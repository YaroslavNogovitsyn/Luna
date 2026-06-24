import argparse
import pathlib
import sys

from uvicorn import run


if __name__ == '__main__':
    # Получение параметров запуска
    parser = argparse.ArgumentParser('python run.py -hs 0.0.0.0 -p 8000 -w 16')

    # Адрес запускаемого сервера
    parser.add_argument(
        '-hs',
        '--host',
        help='Server address host',
        type=str,
        required=False,
        default='127.0.0.1',
    )

    # Порт запускаемого сервера
    parser.add_argument(
        '-p',
        '--port',
        help='Server address port',
        type=int,
        required=False,
        default=8000,
    )

    # Кол-во запускаемых воркеров (подпроцессов)
    parser.add_argument(
        '-w',
        '--workers',
        help='Amount of UVICORN workers',
        type=int,
        required=False,
        # Получение количества потоков vCPU
        # num_threads (кол-во потоков процессора) + 1 (управляющий worker)
        default=1,
    )

    # Парсинг переданных параметров запуска
    args = parser.parse_args()

    # Отладочный вывод информации
    sys.stdout.write(f'Running app (UVICORN) on {args.host}:{args.port} with {args.workers} workers\n')

    # Запуск веб-сервера UVICORN
    run(
        app='payments.main:create_app',
        app_dir=str(pathlib.Path.cwd()),
        host=args.host,
        port=args.port,
        workers=args.workers,
        factory=True,
    )
