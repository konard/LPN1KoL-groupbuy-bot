<?php

namespace App\Exceptions;

use Illuminate\Foundation\Exceptions\Handler as ExceptionHandler;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Throwable;

final class Handler extends ExceptionHandler
{
    public function render($request, Throwable $e)
    {
        if ($request instanceof Request && $request->expectsJson()) {
            return new JsonResponse([
                'code' => class_basename($e),
                'message' => $e->getMessage(),
                'errors' => [],
            ], $this->statusCode($e));
        }

        return parent::render($request, $e);
    }

    private function statusCode(Throwable $e): int
    {
        return match (true) {
            $e instanceof IdempotencyViolationException => 409,
            $e instanceof ReadingValidationException => 422,
            $e instanceof TariffExpiredException => 422,
            $e instanceof BillAlreadyPaidException => 409,
            $e instanceof NotificationDispatchException => 502,
            $e instanceof InsufficientDataException => 422,
            default => 500,
        };
    }
}
