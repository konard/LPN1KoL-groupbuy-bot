package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	kafkago "github.com/segmentio/kafka-go"
)

type Producer struct {
	writer *kafkago.Writer
}

func NewProducer() *Producer {
	brokers := strings.Split(getEnv("KAFKA_BROKERS", "localhost:9092"), ",")
	w := &kafkago.Writer{
		Addr:                   kafkago.TCP(brokers...),
		Balancer:               &kafkago.LeastBytes{},
		AllowAutoTopicCreation: true,
		Compression:            kafkago.Gzip,
		WriteTimeout:           10 * time.Second,
		ReadTimeout:            10 * time.Second,
		RequiredAcks:           kafkago.RequireOne,
	}
	return &Producer{writer: w}
}

func (p *Producer) Send(ctx context.Context, topic string, key string, payload map[string]any) error {
	payload["timestamp"] = time.Now().UTC().Format(time.RFC3339)
	payload["service"] = "payment-service"

	value, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	msg := kafkago.Message{
		Topic: topic,
		Value: value,
	}
	if key != "" {
		msg.Key = []byte(key)
	}

	err = p.writer.WriteMessages(ctx, msg)
	if err != nil {
		log.Printf("Kafka send error topic=%s: %v", topic, err)
		return err
	}
	return nil
}

func (p *Producer) Close() error {
	return p.writer.Close()
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
