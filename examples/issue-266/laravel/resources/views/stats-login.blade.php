<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Visitor stats login</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: Arial, sans-serif;
            background: #f3f5f7;
            color: #1f2937;
        }

        form {
            width: min(360px, calc(100vw - 32px));
            display: grid;
            gap: 16px;
            padding: 24px;
            background: #ffffff;
            border: 1px solid #d8dee4;
            border-radius: 8px;
        }

        input,
        button {
            min-height: 40px;
            font: inherit;
        }

        input {
            padding: 0 12px;
            border: 1px solid #c9d1d9;
            border-radius: 6px;
        }

        button {
            border: 0;
            border-radius: 6px;
            background: #2563eb;
            color: #ffffff;
            cursor: pointer;
        }

        .error {
            color: #b91c1c;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <form method="post" action="/stats/login">
        @csrf
        <h1>Статистика посещений</h1>
        <input type="password" name="password" placeholder="Пароль" required autofocus>
        @error('password')
            <div class="error">{{ $message }}</div>
        @enderror
        <button type="submit">Войти</button>
    </form>
</body>
</html>
