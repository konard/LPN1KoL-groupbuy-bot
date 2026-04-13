package indexer

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/olivere/elastic/v7"
	kafkago "github.com/segmentio/kafka-go"

	"search-service/models"
)

const purchasesIndex = "purchases"

const purchasesMapping = `{
	"settings": {
		"number_of_shards": 1,
		"number_of_replicas": 0,
		"analysis": {
			"analyzer": {
				"text_analyzer": {
					"type": "custom",
					"tokenizer": "standard",
					"filter": ["lowercase", "asciifolding"]
				}
			}
		}
	},
	"mappings": {
		"properties": {
			"title": {
				"type": "text",
				"analyzer": "text_analyzer",
				"fields": {
					"keyword": { "type": "keyword" }
				}
			},
			"description": {
				"type": "text",
				"analyzer": "text_analyzer"
			},
			"category": {
				"type": "text",
				"analyzer": "text_analyzer",
				"fields": {
					"keyword": { "type": "keyword" }
				}
			},
			"city": {
				"type": "text",
				"analyzer": "text_analyzer",
				"fields": {
					"keyword": { "type": "keyword" }
				}
			},
			"price": {
				"type": "float"
			},
			"organizer": {
				"type": "text",
				"analyzer": "text_analyzer",
				"fields": {
					"keyword": { "type": "keyword" }
				}
			},
			"status": {
				"type": "keyword"
			},
			"created_at": {
				"type": "date"
			},
			"updated_at": {
				"type": "date"
			}
		}
	}
}`

type Indexer struct {
	es     *elastic.Client
	reader *kafkago.Reader
}

func NewIndexer(es *elastic.Client) *Indexer {
	brokers := strings.Split(getEnv("KAFKA_BROKERS", "localhost:9092"), ",")

	reader := kafkago.NewReader(kafkago.ReaderConfig{
		Brokers:        brokers,
		GroupID:        "search-indexer",
		GroupTopics:    []string{"purchase.created", "purchase.updated"},
		MinBytes:       1,
		MaxBytes:       10e6,
		MaxWait:        1 * time.Second,
		CommitInterval: 1 * time.Second,
		StartOffset:    kafkago.LastOffset,
	})

	return &Indexer{es: es, reader: reader}
}

func (idx *Indexer) EnsureIndex(ctx context.Context) error {
	exists, err := idx.es.IndexExists(purchasesIndex).Do(ctx)
	if err != nil {
		return fmt.Errorf("check index existence: %w", err)
	}

	if !exists {
		createResult, err := idx.es.CreateIndex(purchasesIndex).Body(purchasesMapping).Do(ctx)
		if err != nil {
			return fmt.Errorf("create index: %w", err)
		}
		if !createResult.Acknowledged {
			return fmt.Errorf("index creation not acknowledged")
		}
		log.Printf("Created Elasticsearch index: %s", purchasesIndex)
	} else {
		log.Printf("Elasticsearch index already exists: %s", purchasesIndex)
	}

	return nil
}

func (idx *Indexer) Start(ctx context.Context) {
	log.Println("Indexer: starting Kafka consumer for purchase events")

	for {
		select {
		case <-ctx.Done():
			log.Println("Indexer: shutting down")
			return
		default:
		}

		msg, err := idx.reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			log.Printf("Indexer: fetch message error: %v", err)
			time.Sleep(1 * time.Second)
			continue
		}

		if err := idx.processMessage(ctx, msg); err != nil {
			log.Printf("Indexer: process message error (topic=%s, offset=%d): %v",
				msg.Topic, msg.Offset, err)
			// Still commit to avoid reprocessing a permanently broken message
		}

		if err := idx.reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("Indexer: commit error: %v", err)
		}
	}
}

func (idx *Indexer) processMessage(ctx context.Context, msg kafkago.Message) error {
	var event models.PurchaseEvent
	if err := json.Unmarshal(msg.Value, &event); err != nil {
		return fmt.Errorf("unmarshal purchase event: %w", err)
	}

	if event.ID == "" {
		return fmt.Errorf("purchase event missing ID")
	}

	doc := map[string]any{
		"title":       event.Title,
		"description": event.Description,
		"category":    event.Category,
		"city":        event.City,
		"price":       event.Price,
		"organizer":   event.Organizer,
		"status":      event.Status,
		"updated_at":  time.Now().UTC().Format(time.RFC3339),
	}

	if msg.Topic == "purchase.created" {
		doc["created_at"] = time.Now().UTC().Format(time.RFC3339)
	}

	_, err := idx.es.Index().
		Index(purchasesIndex).
		Id(event.ID).
		BodyJson(doc).
		Do(ctx)
	if err != nil {
		return fmt.Errorf("index document %s: %w", event.ID, err)
	}

	log.Printf("Indexer: indexed purchase %s (topic=%s)", event.ID, msg.Topic)
	return nil
}

func (idx *Indexer) Close() error {
	return idx.reader.Close()
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
