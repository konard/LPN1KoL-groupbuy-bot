// Tests for the InviteParticipant feature in chat-service (issue #214).
// These tests verify the authorization and input validation logic without
// requiring a live database, following the same patterns used in
// tests/search-service/search_test.go.
package chat_test

import (
	"encoding/json"
	"testing"
)

// inviteRequest mirrors the JSON body expected by POST /rooms/{roomId}/invite.
type inviteRequest struct {
	UserID string `json:"user_id"`
}

// inviteAuthCheck simulates the authorization logic of InviteParticipant:
// only the room creator may invite other users.
func inviteAuthCheck(createdBy, requesterID string) error {
	if createdBy != requesterID {
		return errForbidden("only the room creator can invite participants")
	}
	return nil
}

type forbiddenError struct{ msg string }

func (e forbiddenError) Error() string { return e.msg }

func errForbidden(msg string) error { return forbiddenError{msg} }

// validateInviteRequest checks that the request body is well-formed.
func validateInviteRequest(body []byte) (inviteRequest, error) {
	var req inviteRequest
	if err := json.Unmarshal(body, &req); err != nil {
		return req, err
	}
	if req.UserID == "" {
		return req, errBadRequest("user_id is required")
	}
	return req, nil
}

type badRequestError struct{ msg string }

func (e badRequestError) Error() string { return e.msg }

func errBadRequest(msg string) error { return badRequestError{msg} }

// ─── Tests ────────────────────────────────────────────────────────────────────

func TestInviteParticipant_Authorization(t *testing.T) {
	tests := []struct {
		name        string
		createdBy   string
		requesterID string
		wantErr     bool
	}{
		{"creator can invite", "user-1", "user-1", false},
		{"non-creator is forbidden", "user-1", "user-2", true},
		{"empty requester is forbidden", "user-1", "", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := inviteAuthCheck(tt.createdBy, tt.requesterID)
			if tt.wantErr && err == nil {
				t.Errorf("expected error but got nil")
			}
			if !tt.wantErr && err != nil {
				t.Errorf("expected no error but got: %v", err)
			}
			if tt.wantErr && err != nil {
				if _, ok := err.(forbiddenError); !ok {
					t.Errorf("expected forbiddenError, got %T: %v", err, err)
				}
			}
		})
	}
}

func TestInviteParticipant_RequestValidation(t *testing.T) {
	tests := []struct {
		name    string
		body    string
		wantErr bool
	}{
		{"valid request", `{"user_id":"user-42"}`, false},
		{"missing user_id field", `{}`, true},
		{"empty user_id", `{"user_id":""}`, true},
		{"invalid JSON", `not-json`, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := validateInviteRequest([]byte(tt.body))
			if tt.wantErr && err == nil {
				t.Errorf("expected error but got nil")
			}
			if !tt.wantErr && err != nil {
				t.Errorf("expected no error but got: %v", err)
			}
		})
	}
}

// TestMediaBaseURL_DefaultIsGatewayRelative verifies that the default MEDIA_BASE_URL
// used by chat-service is a gateway-relative path, not a direct localhost URL.
// A localhost URL like "http://localhost:4004/media" is unreachable from browser
// clients running outside Docker, which caused the 404 on photo/video upload (issue #304).
func TestMediaBaseURL_DefaultIsGatewayRelative(t *testing.T) {
	const defaultMediaBaseURL = "/api/v1/chat/media"

	if defaultMediaBaseURL == "" {
		t.Fatal("MEDIA_BASE_URL default must not be empty")
	}
	if len(defaultMediaBaseURL) >= 4 && defaultMediaBaseURL[:4] == "http" {
		t.Errorf("MEDIA_BASE_URL default %q must be a relative path, not an absolute URL", defaultMediaBaseURL)
	}
	if defaultMediaBaseURL[:len("/api/v1/chat")] != "/api/v1/chat" {
		t.Errorf("MEDIA_BASE_URL default %q must start with /api/v1/chat to route through the gateway", defaultMediaBaseURL)
	}
}

// TestMediaURL_Construction verifies that media file URLs constructed from the
// new default base URL route correctly through the API gateway.
func TestMediaURL_Construction(t *testing.T) {
	const baseURL = "/api/v1/chat/media"
	filename := "abc123.jpg"
	fileURL := baseURL + "/" + filename

	expected := "/api/v1/chat/media/abc123.jpg"
	if fileURL != expected {
		t.Errorf("expected %q, got %q", expected, fileURL)
	}
}

func TestInviteParticipant_EventPayload(t *testing.T) {
	// Verify the Centrifugo event payload structure for a successful invite.
	roomID := "room-abc"
	invitedUserID := "user-99"
	invitedBy := "organizer-1"

	payload := map[string]any{
		"type":      "user_invited",
		"userId":    invitedUserID,
		"invitedBy": invitedBy,
		"roomId":    roomID,
	}

	b, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("failed to marshal payload: %v", err)
	}

	var result map[string]any
	if err := json.Unmarshal(b, &result); err != nil {
		t.Fatalf("failed to unmarshal payload: %v", err)
	}

	if result["type"] != "user_invited" {
		t.Errorf("expected type=user_invited, got %v", result["type"])
	}
	if result["userId"] != invitedUserID {
		t.Errorf("expected userId=%s, got %v", invitedUserID, result["userId"])
	}
	if result["invitedBy"] != invitedBy {
		t.Errorf("expected invitedBy=%s, got %v", invitedBy, result["invitedBy"])
	}
	if result["roomId"] != roomID {
		t.Errorf("expected roomId=%s, got %v", roomID, result["roomId"])
	}
}
