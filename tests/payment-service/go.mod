module payment_test

go 1.22

require (
	github.com/google/uuid v1.6.0
	payment-service v0.0.0
)

replace payment-service => ../../services/payment-service
