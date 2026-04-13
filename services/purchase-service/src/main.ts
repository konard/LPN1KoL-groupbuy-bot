import { NestFactory, HttpAdapterHost } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import { AllExceptionsFilter } from './filters/all-exceptions.filter';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Strict validation: strip unknown fields + reject requests with extra fields
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,                  // Strip fields not declared in DTO
      forbidNonWhitelisted: true,       // Reject requests with unexpected extra fields
      transform: true,                  // Auto-convert primitive types
      transformOptions: {
        enableImplicitConversion: true,
      },
    }),
  );

  // Global exception filter: always returns structured { status, code, message }
  // Never returns an empty 500 Internal Server Error
  const { httpAdapter } = app.get(HttpAdapterHost);
  app.useGlobalFilters(new AllExceptionsFilter(httpAdapter));

  const port = process.env.PORT ?? 4002;
  await app.listen(port);
  console.log(`Purchase service running on port ${port}`);
}

bootstrap();
