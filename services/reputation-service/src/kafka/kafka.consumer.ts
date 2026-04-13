import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';
import { ReviewsService } from '../reviews/reviews.service';
import { ReviewRole } from '../reviews/reviews.entity';

interface PurchaseCompletedEvent {
  purchaseId: string;
  organizerId: string;
  supplierId?: string;
  buyerIds: string[];
  completedAt: string;
}

@Injectable()
export class KafkaConsumer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaConsumer.name);
  private consumer: Consumer;

  constructor(
    private readonly configService: ConfigService,
    private readonly reviewsService: ReviewsService,
  ) {
    const brokers = (this.configService.get<string>('KAFKA_BROKERS', 'localhost:9092'))
      .split(',');
    const clientId = this.configService.get<string>('KAFKA_CLIENT_ID', 'reputation-service');
    const groupId = this.configService.get<string>('KAFKA_GROUP_ID', 'reputation-service-group');

    const kafka = new Kafka({
      clientId,
      brokers,
      retry: {
        initialRetryTime: 300,
        retries: 8,
      },
    });

    this.consumer = kafka.consumer({ groupId });
  }

  async onModuleInit(): Promise<void> {
    try {
      await this.consumer.connect();
      await this.consumer.subscribe({
        topic: 'purchase.completed',
        fromBeginning: false,
      });

      await this.consumer.run({
        eachMessage: async (payload: EachMessagePayload) => {
          await this.handleMessage(payload);
        },
      });

      this.logger.log('Kafka consumer connected and subscribed to purchase.completed');
    } catch (err) {
      this.logger.error(`Failed to start Kafka consumer: ${err}`);
    }
  }

  async onModuleDestroy(): Promise<void> {
    try {
      await this.consumer.disconnect();
    } catch (err) {
      this.logger.error(`Failed to disconnect Kafka consumer: ${err}`);
    }
  }

  private async handleMessage(payload: EachMessagePayload): Promise<void> {
    const { topic, message } = payload;

    if (!message.value) {
      this.logger.warn(`Received empty message on topic ${topic}`);
      return;
    }

    try {
      const event: PurchaseCompletedEvent = JSON.parse(message.value.toString());

      this.logger.log(
        `Processing purchase.completed event: purchaseId=${event.purchaseId}`,
      );

      await this.handlePurchaseCompleted(event);
    } catch (err) {
      this.logger.error(
        `Error processing message on topic ${topic}: ${err}`,
      );
    }
  }

  private async handlePurchaseCompleted(event: PurchaseCompletedEvent): Promise<void> {
    const completedAt = new Date(event.completedAt);
    const expiresAt = new Date(completedAt.getTime() + 14 * 24 * 60 * 60 * 1000);

    this.logger.log(
      `Review window opened for purchase ${event.purchaseId}: ` +
      `expires at ${expiresAt.toISOString()}`,
    );

    // The review window is now open. Actual reviews are created via the REST API
    // when users submit them. The expiresAt timestamp is passed to createReview
    // to enforce the 14-day window.
    //
    // In a full implementation, this would also:
    // 1. Store the review window in a dedicated table
    // 2. Send notifications to participants that they can now rate each other
    // 3. Schedule a reminder notification before the window closes
    //
    // For now, we log the event so downstream consumers can pick it up.

    this.logger.log(
      `Review window details: ` +
      `organizer=${event.organizerId}, ` +
      `supplier=${event.supplierId ?? 'none'}, ` +
      `buyers=${event.buyerIds?.length ?? 0}, ` +
      `expiresAt=${expiresAt.toISOString()}`,
    );
  }
}
