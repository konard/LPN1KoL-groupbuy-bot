import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Kafka, Producer, Partitioners, CompressionTypes } from 'kafkajs';

@Injectable()
export class KafkaProducer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaProducer.name);
  private producer: Producer;

  constructor(private readonly configService: ConfigService) {
    const brokers = (this.configService.get<string>('KAFKA_BROKERS', 'localhost:9092'))
      .split(',');
    const clientId = this.configService.get<string>('KAFKA_CLIENT_ID', 'purchase-service');

    const kafka = new Kafka({
      clientId,
      brokers,
      retry: {
        initialRetryTime: 300,
        retries: 8,
      },
    });

    this.producer = kafka.producer({
      createPartitioner: Partitioners.LegacyPartitioner,
      allowAutoTopicCreation: true,
    });
  }

  async onModuleInit(): Promise<void> {
    try {
      await this.producer.connect();
      this.logger.log('Kafka producer connected');
    } catch (err) {
      this.logger.error(`Failed to connect Kafka producer: ${err}`);
    }
  }

  async onModuleDestroy(): Promise<void> {
    await this.producer.disconnect();
  }

  async send(topic: string, payload: Record<string, any>, key?: string): Promise<void> {
    try {
      await this.producer.send({
        topic,
        compression: CompressionTypes.GZIP,
        messages: [
          {
            key: key ?? payload.purchaseId ?? payload.sessionId ?? null,
            value: JSON.stringify({
              ...payload,
              timestamp: new Date().toISOString(),
              service: 'purchase-service',
            }),
          },
        ],
      });
    } catch (err) {
      this.logger.error(`Failed to send Kafka message to ${topic}: ${err}`);
      // Non-fatal: log and continue
    }
  }
}
