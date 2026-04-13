import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { AbstractHttpAdapter } from '@nestjs/core';
import { ValidationError } from 'class-validator';

/**
 * Global exception filter that converts all exceptions into structured JSON responses:
 * { "status": <http_code>, "code": "<MACHINE_CODE>", "message": "<human message>" }
 *
 * This prevents empty 500 Internal Server Error responses from ever reaching the client.
 */
@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  constructor(private readonly httpAdapter: AbstractHttpAdapter) {}

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const request = ctx.getRequest();
    const response = ctx.getResponse();

    let httpStatus = HttpStatus.INTERNAL_SERVER_ERROR;
    let code = 'INTERNAL_SERVER_ERROR';
    let message = 'An unexpected error occurred';
    let details: unknown = undefined;

    if (exception instanceof HttpException) {
      httpStatus = exception.getStatus();
      const exceptionResponse = exception.getResponse();

      if (typeof exceptionResponse === 'string') {
        message = exceptionResponse;
        code = this.statusToCode(httpStatus);
      } else if (typeof exceptionResponse === 'object' && exceptionResponse !== null) {
        const resp = exceptionResponse as Record<string, unknown>;
        // Use structured code if already set (e.g. by our ban/auth services)
        code = (resp['code'] as string) ?? this.statusToCode(httpStatus);
        message = (resp['message'] as string) ?? message;
        // class-validator validation errors come as an array
        if (Array.isArray(resp['message'])) {
          message = 'Validation failed';
          details = resp['message'];
          code = 'VALIDATION_ERROR';
        }
      }
    } else if (exception instanceof Error) {
      this.logger.error(
        `Unhandled exception on ${request.method} ${request.url}: ${exception.message}`,
        exception.stack,
      );
      // Do not leak internal error details to the client
      message = 'An unexpected error occurred';
    } else {
      this.logger.error(`Unknown exception type on ${request.method} ${request.url}`, exception);
    }

    const responseBody: Record<string, unknown> = {
      status: httpStatus,
      code,
      message,
    };
    if (details !== undefined) {
      responseBody['details'] = details;
    }

    this.httpAdapter.reply(response, responseBody, httpStatus);
  }

  private statusToCode(status: number): string {
    const map: Record<number, string> = {
      400: 'BAD_REQUEST',
      401: 'UNAUTHORIZED',
      403: 'FORBIDDEN',
      404: 'NOT_FOUND',
      409: 'CONFLICT',
      422: 'UNPROCESSABLE_ENTITY',
      429: 'TOO_MANY_REQUESTS',
      500: 'INTERNAL_SERVER_ERROR',
      503: 'SERVICE_UNAVAILABLE',
    };
    return map[status] ?? 'HTTP_ERROR';
  }
}
