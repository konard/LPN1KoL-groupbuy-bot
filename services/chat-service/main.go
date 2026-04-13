package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	clickhouse "github.com/ClickHouse/clickhouse-go/v2"
	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ─── Models ───────────────────────────────────────────────────────────────────

type Room struct {
	ID         string  `json:"id"`
	Name       string  `json:"name"`
	Type       string  `json:"type"` // "purchase" | "direct" | "group"
	PurchaseID *string `json:"purchase_id,omitempty"`
	CreatedBy  string  `json:"created_by"`
	IsArchived bool    `json:"is_archived"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

// ChatMessage is the API representation of a message.
// Deleted messages return IsDeleted=true and blank Content for non-admins.
type ChatMessage struct {
	ID          string          `json:"id"`
	RoomID      string          `json:"room_id"`
	UserID      string          `json:"user_id"`
	Content     string          `json:"content"`
	Type        string          `json:"type"` // "text" | "system" | "image" | "video" | "file"
	MediaURL    string          `json:"media_url,omitempty"`
	IsEdited    bool            `json:"is_edited"`
	IsDeleted   bool            `json:"is_deleted"`
	EditHistory json.RawMessage `json:"edit_history,omitempty"` // JSONB: [{content, edited_at}]
	CreatedAt   time.Time       `json:"created_at"`
	UpdatedAt   time.Time       `json:"updated_at"`
}

// MediaLibraryEntry is stored in media_library and lives independently of messages.
type MediaLibraryEntry struct {
	ID          string    `json:"id"`
	UploaderID  string    `json:"uploader_id"`
	Filename    string    `json:"filename"`
	OrigName    string    `json:"original_filename"`
	MimeType    string    `json:"mime_type"`
	Size        int64     `json:"size"`
	URL         string    `json:"url"`
	SHA256      string    `json:"sha256"`
	CreatedAt   time.Time `json:"created_at"`
}

// ─── Server ───────────────────────────────────────────────────────────────────

type Server struct {
	db              *pgxpool.Pool
	rdb             *redis.Client
	ch              clickhouse.Conn
	centrifugoURL   string
	centrifugoKey   string
	mediaStorageDir string
	mediaBaseURL    string
}

// Allowed media MIME types, max file size (25 MB) and magic bytes signatures.
const maxMediaSize = 25 << 20 // 25 MB

var allowedMediaTypes = map[string]string{
	"image/jpeg":      "jpg",
	"image/png":       "png",
	"image/gif":       "gif",
	"video/mp4":       "mp4",
	"video/quicktime": "mov",
}

// magicBytes maps MIME type to the required leading bytes (magic bytes).
// Validation against magic bytes prevents Content-Type spoofing.
var magicBytes = map[string][]byte{
	"image/jpeg":      {0xFF, 0xD8, 0xFF},
	"image/png":       {0x89, 0x50, 0x4E, 0x47},
	"image/gif":       {0x47, 0x49, 0x46},
	"video/mp4":       {0x00, 0x00, 0x00}, // checked by ftyp box below
	"video/quicktime": {0x00, 0x00, 0x00},
}

// validateMagicBytes verifies that the file data starts with known magic bytes.
// For MP4/MOV we check for the ftyp ISO box which can appear at offset 4.
func validateMagicBytes(data []byte, mimeType string) bool {
	if len(data) < 8 {
		return false
	}
	switch mimeType {
	case "image/jpeg":
		return bytes.HasPrefix(data, []byte{0xFF, 0xD8, 0xFF})
	case "image/png":
		return bytes.HasPrefix(data, []byte{0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A})
	case "image/gif":
		return bytes.HasPrefix(data, []byte("GIF87a")) || bytes.HasPrefix(data, []byte("GIF89a"))
	case "video/mp4", "video/quicktime":
		// ftyp box: bytes 4-7 are "ftyp"
		return len(data) >= 8 && string(data[4:8]) == "ftyp"
	}
	return false
}

// ─── Centrifugo API ───────────────────────────────────────────────────────────

func (s *Server) centrifugoPublish(channel string, data map[string]any) error {
	payload := map[string]any{
		"method": "publish",
		"params": map[string]any{
			"channel": channel,
			"data":    data,
		},
	}
	body, _ := json.Marshal(payload)
	req, err := http.NewRequest(http.MethodPost, s.centrifugoURL+"/api", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", s.centrifugoKey)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("centrifugo error %d: %s", resp.StatusCode, string(b))
	}
	return nil
}

// ─── Handlers ─────────────────────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code string, msg string) {
	writeJSON(w, status, map[string]any{
		"status":  status,
		"code":    code,
		"message": msg,
	})
}

func (s *Server) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok", "service": "chat-service"})
}

// CreateRoom creates a chat room and registers it in Centrifugo.
func (s *Server) CreateRoom(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	var req struct {
		Name       string  `json:"name"`
		Type       string  `json:"type"`
		PurchaseID *string `json:"purchase_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "invalid JSON")
		return
	}
	if req.Name == "" {
		writeError(w, http.StatusBadRequest, "MISSING_FIELD", "name is required")
		return
	}
	if req.Type == "" {
		req.Type = "group"
	}

	id := uuid.New().String()
	room := &Room{
		ID:         id,
		Name:       req.Name,
		Type:       req.Type,
		PurchaseID: req.PurchaseID,
		CreatedBy:  userID,
		IsArchived: false,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	_, err := s.db.Exec(r.Context(),
		`INSERT INTO rooms (id, name, type, purchase_id, created_by, is_archived, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, FALSE, NOW(), NOW())`,
		room.ID, room.Name, room.Type, room.PurchaseID, room.CreatedBy,
	)
	if err != nil {
		log.Printf("CreateRoom DB error: %v", err)
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to create room")
		return
	}

	// Add creator as member
	if _, err := s.db.Exec(r.Context(),
		`INSERT INTO room_members (room_id, user_id, joined_at) VALUES ($1, $2, NOW())`,
		room.ID, userID,
	); err != nil {
		log.Printf("AddRoomMember DB error: %v", err)
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to add creator as member")
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{"success": true, "data": room})
}

// GetRoom retrieves room details.
func (s *Server) GetRoom(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]

	row := s.db.QueryRow(r.Context(),
		`SELECT id, name, type, purchase_id, created_by, is_archived, created_at, updated_at
		 FROM rooms WHERE id = $1`, roomID)

	room := &Room{}
	err := row.Scan(&room.ID, &room.Name, &room.Type, &room.PurchaseID,
		&room.CreatedBy, &room.IsArchived, &room.CreatedAt, &room.UpdatedAt)
	if err != nil {
		writeError(w, http.StatusNotFound, "ROOM_NOT_FOUND", "room not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": room})
}

// JoinRoom adds a user to a room.
func (s *Server) JoinRoom(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	_, err := s.db.Exec(r.Context(),
		`INSERT INTO room_members (room_id, user_id, joined_at)
		 VALUES ($1, $2, NOW()) ON CONFLICT DO NOTHING`,
		roomID, userID,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to join room")
		return
	}

	channel := "chat:" + roomID
	s.centrifugoPublish(channel, map[string]any{
		"type":   "user_joined",
		"userId": userID,
		"roomId": roomID,
	})

	writeJSON(w, http.StatusOK, map[string]any{"success": true})
}

// InviteParticipant allows the room creator to invite another user to the room.
func (s *Server) InviteParticipant(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	requesterID := r.Header.Get("X-User-ID")
	if requesterID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	var req struct {
		UserID string `json:"user_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "invalid JSON")
		return
	}
	if req.UserID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_FIELD", "user_id is required")
		return
	}

	var createdBy string
	row := s.db.QueryRow(r.Context(), `SELECT created_by FROM rooms WHERE id = $1`, roomID)
	if err := row.Scan(&createdBy); err != nil {
		writeError(w, http.StatusNotFound, "ROOM_NOT_FOUND", "room not found")
		return
	}
	if createdBy != requesterID {
		writeError(w, http.StatusForbidden, "INVITE_FORBIDDEN", "only the room creator can invite participants")
		return
	}

	_, err := s.db.Exec(r.Context(),
		`INSERT INTO room_members (room_id, user_id, joined_at)
		 VALUES ($1, $2, NOW()) ON CONFLICT DO NOTHING`,
		roomID, req.UserID,
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to invite participant")
		return
	}

	channel := "chat:" + roomID
	s.centrifugoPublish(channel, map[string]any{
		"type":      "user_invited",
		"userId":    req.UserID,
		"invitedBy": requesterID,
		"roomId":    roomID,
	})

	writeJSON(w, http.StatusOK, map[string]any{"success": true})
}

// UploadMedia handles multipart file upload:
//   - Validates magic bytes (not just Content-Type header)
//   - Stores file in independent media_library (not tied to a message)
//   - Returns media_library entry; caller embeds the URL in a message
func (s *Server) UploadMedia(w http.ResponseWriter, r *http.Request) {
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	// Limit total request body to avoid memory exhaustion (5 files * 25 MB + overhead)
	r.Body = http.MaxBytesReader(w, r.Body, 5*maxMediaSize+1<<20)

	if err := r.ParseMultipartForm(5 * maxMediaSize); err != nil {
		writeError(w, http.StatusBadRequest, "PARSE_ERROR", "failed to parse multipart form: "+err.Error())
		return
	}

	files := r.MultipartForm.File["files"]
	if len(files) == 0 {
		writeError(w, http.StatusBadRequest, "NO_FILES", "no files provided")
		return
	}
	if len(files) > 5 {
		writeError(w, http.StatusBadRequest, "TOO_MANY_FILES", "maximum 5 files per request")
		return
	}

	results := make([]MediaLibraryEntry, 0, len(files))

	for _, fh := range files {
		if fh.Size > maxMediaSize {
			writeError(w, http.StatusBadRequest, "FILE_TOO_LARGE",
				fmt.Sprintf("file %s exceeds 25 MB limit", fh.Filename))
			return
		}

		// Detect MIME type from content type header or file extension
		detectedType := fh.Header.Get("Content-Type")
		if detectedType == "" {
			ext := strings.ToLower(filepath.Ext(fh.Filename))
			detectedType = mime.TypeByExtension(ext)
		}
		mediaType, _, _ := mime.ParseMediaType(detectedType)

		ext, allowed := allowedMediaTypes[mediaType]
		if !allowed {
			writeError(w, http.StatusBadRequest, "FILE_TYPE_NOT_ALLOWED",
				fmt.Sprintf("file type %s not allowed; use JPEG, PNG, GIF, MP4, or MOV", mediaType))
			return
		}

		f, err := fh.Open()
		if err != nil {
			writeError(w, http.StatusInternalServerError, "READ_ERROR", "failed to read uploaded file")
			return
		}
		defer func(file multipart.File) { file.Close() }(f)

		data, err := io.ReadAll(io.LimitReader(f, maxMediaSize+1))
		if err != nil {
			writeError(w, http.StatusInternalServerError, "READ_ERROR", "failed to read file data")
			return
		}

		// CRITICAL: Validate magic bytes — Content-Type header can be spoofed
		if !validateMagicBytes(data, mediaType) {
			writeError(w, http.StatusBadRequest, "INVALID_FILE_CONTENT",
				fmt.Sprintf("file %s content does not match declared type %s", fh.Filename, mediaType))
			return
		}

		// Compute SHA-256 for deduplication
		fileHash := computeSHA256(data)

		// Save to local storage directory
		filename := uuid.New().String() + "." + ext
		savePath := filepath.Join(s.mediaStorageDir, filename)
		if err := os.WriteFile(savePath, data, 0644); err != nil {
			log.Printf("UploadMedia write error: %v", err)
			writeError(w, http.StatusInternalServerError, "WRITE_ERROR", "failed to save file")
			return
		}

		mediaURL := s.mediaBaseURL + "/" + filename
		entryID := uuid.New().String()

		// Persist in media_library — lives independently of any chat message
		_, err = s.db.Exec(r.Context(),
			`INSERT INTO media_library
			   (id, uploader_id, filename, original_filename, mime_type, size, url, sha256, created_at)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())`,
			entryID, userID, filename, fh.Filename, mediaType, fh.Size, mediaURL, fileHash,
		)
		if err != nil {
			log.Printf("UploadMedia media_library insert error: %v", err)
			writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to register media")
			return
		}

		results = append(results, MediaLibraryEntry{
			ID:         entryID,
			UploaderID: userID,
			Filename:   filename,
			OrigName:   fh.Filename,
			MimeType:   mediaType,
			Size:       fh.Size,
			URL:        mediaURL,
			SHA256:     fileHash,
		})
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": results})
}

// ServeMedia serves uploaded media files from storage directory.
func (s *Server) ServeMedia(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	filename := vars["filename"]
	if strings.Contains(filename, "/") || strings.Contains(filename, "..") {
		writeError(w, http.StatusBadRequest, "INVALID_FILENAME", "invalid filename")
		return
	}
	http.ServeFile(w, r, filepath.Join(s.mediaStorageDir, filename))
}

// SendMessage saves a message to PostgreSQL (not just ClickHouse) for durability,
// then publishes to Centrifugo for real-time delivery.
// Idempotency key prevents duplicate messages on retry.
func (s *Server) SendMessage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	var req struct {
		Content        string `json:"content"`
		Type           string `json:"type"`
		MediaURL       string `json:"media_url"`
		IdempotencyKey string `json:"idempotency_key"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "invalid JSON")
		return
	}
	if req.Content == "" && req.MediaURL == "" {
		writeError(w, http.StatusBadRequest, "MISSING_CONTENT", "content or media_url is required")
		return
	}
	if req.Type == "" {
		if req.MediaURL != "" {
			req.Type = "file"
		} else {
			req.Type = "text"
		}
	}

	// Idempotency: if key provided and already processed, return cached result
	if req.IdempotencyKey != "" {
		cached, err := s.rdb.Get(r.Context(), "msg:idem:"+req.IdempotencyKey).Result()
		if err == nil && cached != "" {
			// Already processed; return the cached message ID
			writeJSON(w, http.StatusOK, map[string]any{
				"success":     true,
				"idempotent":  true,
				"message_id":  cached,
			})
			return
		}
	}

	// Verify user is member
	var count int
	row := s.db.QueryRow(r.Context(),
		`SELECT COUNT(*) FROM room_members WHERE room_id = $1 AND user_id = $2`, roomID, userID)
	if err := row.Scan(&count); err != nil {
		log.Printf("SendMessage membership check error: %v", err)
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to verify membership")
		return
	}
	if count == 0 {
		writeError(w, http.StatusForbidden, "NOT_A_MEMBER", "not a room member")
		return
	}

	msgID := uuid.New().String()
	now := time.Now()

	// Persist in PostgreSQL for guaranteed durability + soft-delete support
	_, err := s.db.Exec(r.Context(),
		`INSERT INTO messages
		   (id, room_id, user_id, content, type, media_url,
		    is_edited, is_deleted, edit_history, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, FALSE, FALSE, '[]'::jsonb, $7, $7)`,
		msgID, roomID, userID, req.Content, req.Type, req.MediaURL, now,
	)
	if err != nil {
		log.Printf("SendMessage DB insert error: %v", err)
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to save message")
		return
	}

	// Cache idempotency key for 24 h to absorb retries
	if req.IdempotencyKey != "" {
		s.rdb.Set(r.Context(), "msg:idem:"+req.IdempotencyKey, msgID, 24*time.Hour)
	}

	// Mirror to ClickHouse for analytics (non-fatal)
	if s.ch != nil {
		if err := s.ch.Exec(r.Context(),
			`INSERT INTO chat_messages (id, room_id, user_id, content, type, media_url, created_at)
			 VALUES (?, ?, ?, ?, ?, ?, ?)`,
			msgID, roomID, userID, req.Content, req.Type, req.MediaURL, now,
		); err != nil {
			log.Printf("ClickHouse insert error (non-fatal): %v", err)
		}
	}

	// Publish to Centrifugo for real-time delivery
	channel := "chat:" + roomID
	if err := s.centrifugoPublish(channel, map[string]any{
		"type":     "message",
		"id":       msgID,
		"userId":   userID,
		"content":  req.Content,
		"msgType":  req.Type,
		"mediaUrl": req.MediaURL,
		"ts":       now.Unix(),
	}); err != nil {
		log.Printf("Centrifugo publish error: %v", err)
	}

	msg := &ChatMessage{
		ID:        msgID,
		RoomID:    roomID,
		UserID:    userID,
		Content:   req.Content,
		Type:      req.Type,
		MediaURL:  req.MediaURL,
		IsEdited:  false,
		IsDeleted: false,
		CreatedAt: now,
		UpdatedAt: now,
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": msg})
}

// EditMessage edits message content, preserving history in edit_history JSONB column.
// Only the original sender can edit. Editing is allowed for 24 h after creation.
func (s *Server) EditMessage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	msgID := vars["messageId"]
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	var req struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "invalid JSON")
		return
	}
	if strings.TrimSpace(req.Content) == "" {
		writeError(w, http.StatusBadRequest, "MISSING_CONTENT", "content is required")
		return
	}

	// Load existing message
	var (
		ownerID     string
		oldContent  string
		isDeleted   bool
		editHistory json.RawMessage
		createdAt   time.Time
	)
	row := s.db.QueryRow(r.Context(),
		`SELECT user_id, content, is_deleted, edit_history, created_at
		 FROM messages WHERE id = $1 AND room_id = $2`, msgID, roomID)
	if err := row.Scan(&ownerID, &oldContent, &isDeleted, &editHistory, &createdAt); err != nil {
		writeError(w, http.StatusNotFound, "MESSAGE_NOT_FOUND", "message not found")
		return
	}
	if isDeleted {
		writeError(w, http.StatusGone, "MESSAGE_DELETED", "cannot edit a deleted message")
		return
	}
	if ownerID != userID {
		writeError(w, http.StatusForbidden, "EDIT_FORBIDDEN", "only the message author can edit")
		return
	}
	if time.Since(createdAt) > 24*time.Hour {
		writeError(w, http.StatusForbidden, "EDIT_TIME_EXPIRED", "editing is only allowed within 24 hours of sending")
		return
	}

	// Append previous version to edit_history
	type historyEntry struct {
		Content  string `json:"content"`
		EditedAt string `json:"edited_at"`
	}
	var history []historyEntry
	if len(editHistory) > 0 {
		json.Unmarshal(editHistory, &history)
	}
	history = append(history, historyEntry{Content: oldContent, EditedAt: time.Now().UTC().Format(time.RFC3339)})
	newHistory, _ := json.Marshal(history)

	_, err := s.db.Exec(r.Context(),
		`UPDATE messages
		 SET content = $1, is_edited = TRUE, edit_history = $2, updated_at = NOW()
		 WHERE id = $3 AND room_id = $4`,
		req.Content, newHistory, msgID, roomID,
	)
	if err != nil {
		log.Printf("EditMessage DB error: %v", err)
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to edit message")
		return
	}

	channel := "chat:" + roomID
	s.centrifugoPublish(channel, map[string]any{
		"type":      "message_edited",
		"id":        msgID,
		"content":   req.Content,
		"is_edited": true,
		"ts":        time.Now().Unix(),
	})

	writeJSON(w, http.StatusOK, map[string]any{"success": true})
}

// DeleteMessage soft-deletes a message (is_deleted=true, content blanked for regular users).
// Physical deletion never happens; admin/logs can still read original via edit_history.
func (s *Server) DeleteMessage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	msgID := vars["messageId"]
	userID := r.Header.Get("X-User-ID")
	isAdmin := r.Header.Get("X-Is-Admin") == "true"
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	var ownerID string
	row := s.db.QueryRow(r.Context(),
		`SELECT user_id FROM messages WHERE id = $1 AND room_id = $2`, msgID, roomID)
	if err := row.Scan(&ownerID); err != nil {
		writeError(w, http.StatusNotFound, "MESSAGE_NOT_FOUND", "message not found")
		return
	}
	if ownerID != userID && !isAdmin {
		writeError(w, http.StatusForbidden, "DELETE_FORBIDDEN", "only the message author or admin can delete")
		return
	}

	_, err := s.db.Exec(r.Context(),
		`UPDATE messages SET is_deleted = TRUE, updated_at = NOW() WHERE id = $1`, msgID)
	if err != nil {
		log.Printf("DeleteMessage DB error: %v", err)
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to delete message")
		return
	}

	channel := "chat:" + roomID
	s.centrifugoPublish(channel, map[string]any{
		"type": "message_deleted",
		"id":   msgID,
		"ts":   time.Now().Unix(),
	})

	writeJSON(w, http.StatusOK, map[string]any{"success": true})
}

// MarkRead records the last-read message for a user, buffered through Redis.
// Redis is written immediately; PostgreSQL is updated asynchronously every 10 s by a background goroutine.
// This prevents hammering PostgreSQL with UPDATE on every message scroll.
func (s *Server) MarkRead(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	userID := r.Header.Get("X-User-ID")
	if userID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_USER_ID", "X-User-ID required")
		return
	}

	var req struct {
		LastMessageID string `json:"last_message_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "invalid JSON")
		return
	}
	if req.LastMessageID == "" {
		writeError(w, http.StatusBadRequest, "MISSING_FIELD", "last_message_id is required")
		return
	}

	// Write to Redis — fast; PostgreSQL will be updated in background flush
	key := fmt.Sprintf("read:%s:%s", userID, roomID)
	if err := s.rdb.Set(r.Context(), key, req.LastMessageID, 48*time.Hour).Err(); err != nil {
		log.Printf("MarkRead Redis error: %v", err)
		// Fall back to synchronous PostgreSQL update
		s.db.Exec(r.Context(),
			`INSERT INTO message_reads (user_id, room_id, last_message_id, updated_at)
			 VALUES ($1, $2, $3, NOW())
			 ON CONFLICT (user_id, room_id)
			 DO UPDATE SET last_message_id = EXCLUDED.last_message_id, updated_at = NOW()`,
			userID, roomID, req.LastMessageID,
		)
	}

	writeJSON(w, http.StatusOK, map[string]any{"success": true})
}

// flushReadReceiptsToPostgres periodically flushes Redis read-receipt cache to PostgreSQL.
// This is the async write path that keeps DB load minimal.
func (s *Server) flushReadReceiptsToPostgres(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			keys, err := s.rdb.Keys(ctx, "read:*").Result()
			if err != nil {
				log.Printf("flushReadReceipts scan error: %v", err)
				continue
			}
			for _, key := range keys {
				parts := strings.SplitN(strings.TrimPrefix(key, "read:"), ":", 2)
				if len(parts) != 2 {
					continue
				}
				userID, roomID := parts[0], parts[1]
				msgID, err := s.rdb.Get(ctx, key).Result()
				if err != nil {
					continue
				}
				s.db.Exec(ctx,
					`INSERT INTO message_reads (user_id, room_id, last_message_id, updated_at)
					 VALUES ($1, $2, $3, NOW())
					 ON CONFLICT (user_id, room_id)
					 DO UPDATE SET last_message_id = EXCLUDED.last_message_id, updated_at = NOW()`,
					userID, roomID, msgID,
				)
			}
		}
	}
}

// GetHistory retrieves message history from PostgreSQL (persistent store).
// Deleted messages are returned with is_deleted=true and blank content for regular users.
// Admins (X-Is-Admin: true) receive the original content.
func (s *Server) GetHistory(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	isAdmin := r.Header.Get("X-Is-Admin") == "true"

	rows, err := s.db.Query(r.Context(),
		`SELECT id, room_id, user_id, content, type, media_url,
		        is_edited, is_deleted, edit_history, created_at, updated_at
		 FROM messages
		 WHERE room_id = $1
		 ORDER BY created_at DESC
		 LIMIT 100`, roomID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "DB_ERROR", "failed to query history")
		return
	}
	defer rows.Close()

	var messages []ChatMessage
	for rows.Next() {
		var msg ChatMessage
		var editHistoryRaw []byte
		if err := rows.Scan(
			&msg.ID, &msg.RoomID, &msg.UserID, &msg.Content, &msg.Type, &msg.MediaURL,
			&msg.IsEdited, &msg.IsDeleted, &editHistoryRaw, &msg.CreatedAt, &msg.UpdatedAt,
		); err != nil {
			continue
		}
		if len(editHistoryRaw) > 0 {
			msg.EditHistory = json.RawMessage(editHistoryRaw)
		}
		// Non-admins see only the tombstone for deleted messages
		if msg.IsDeleted && !isAdmin {
			msg.Content = ""
			msg.MediaURL = ""
			msg.EditHistory = nil
		}
		messages = append(messages, msg)
	}
	if messages == nil {
		messages = []ChatMessage{}
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": messages})
}

// GetMessage retrieves a single message by ID.
// Returns message_deleted status when the message is deleted (not 500).
func (s *Server) GetMessage(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roomID := vars["roomId"]
	msgID := vars["messageId"]
	isAdmin := r.Header.Get("X-Is-Admin") == "true"

	var msg ChatMessage
	var editHistoryRaw []byte
	row := s.db.QueryRow(r.Context(),
		`SELECT id, room_id, user_id, content, type, media_url,
		        is_edited, is_deleted, edit_history, created_at, updated_at
		 FROM messages WHERE id = $1 AND room_id = $2`, msgID, roomID)
	if err := row.Scan(
		&msg.ID, &msg.RoomID, &msg.UserID, &msg.Content, &msg.Type, &msg.MediaURL,
		&msg.IsEdited, &msg.IsDeleted, &editHistoryRaw, &msg.CreatedAt, &msg.UpdatedAt,
	); err != nil {
		writeError(w, http.StatusNotFound, "MESSAGE_NOT_FOUND", "message not found")
		return
	}
	if len(editHistoryRaw) > 0 {
		msg.EditHistory = json.RawMessage(editHistoryRaw)
	}
	if msg.IsDeleted && !isAdmin {
		msg.Content = ""
		msg.MediaURL = ""
		msg.EditHistory = nil
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true, "data": msg})
}

// ─── SHA-256 helper ───────────────────────────────────────────────────────────

func computeSHA256(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	ctx := context.Background()

	// PostgreSQL
	dsn := getEnv("DATABASE_URL", "postgresql://chat_user:chat_password@localhost:5432/chat_db")
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		log.Fatalf("DB connect failed: %v", err)
	}
	defer pool.Close()

	// Redis — used for read-receipt buffering and message idempotency.
	// Fallback uses the "redis" service name, not localhost, which is incorrect inside Docker containers.
	redisAddr := getEnv("REDIS_URL", "redis://redis:6379")
	opt, err := redis.ParseURL(redisAddr)
	if err != nil {
		log.Fatalf("Redis URL parse failed: %v", err)
	}
	rdb := redis.NewClient(opt)
	// Retry Redis connection up to 3 times before giving up (fail fast on misconfiguration).
	const redisMaxRetries = 3
	redisReady := false
	for i := 1; i <= redisMaxRetries; i++ {
		if _, pingErr := rdb.Ping(ctx).Result(); pingErr == nil {
			redisReady = true
			log.Printf("Connected to Redis at %s", redisAddr)
			break
		} else {
			log.Printf("Redis connect attempt %d/%d failed: %v", i, redisMaxRetries, pingErr)
			if i < redisMaxRetries {
				time.Sleep(2 * time.Second)
			}
		}
	}
	if !redisReady {
		log.Fatalf("Redis unavailable after %d attempts — check REDIS_URL (%s). Aborting.", redisMaxRetries, redisAddr)
	}
	defer rdb.Close()

	// Run PostgreSQL migrations
	pool.Exec(ctx, `
		CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

		CREATE TABLE IF NOT EXISTS rooms (
			id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
			name        VARCHAR(500) NOT NULL,
			type        VARCHAR(50) NOT NULL DEFAULT 'group',
			purchase_id UUID,
			created_by  UUID NOT NULL,
			is_archived BOOLEAN NOT NULL DEFAULT FALSE,
			created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
		);

		CREATE TABLE IF NOT EXISTS room_members (
			room_id   UUID NOT NULL,
			user_id   UUID NOT NULL,
			joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			PRIMARY KEY (room_id, user_id)
		);

		-- Persistent message store with soft-delete and edit history
		CREATE TABLE IF NOT EXISTS messages (
			id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
			room_id      UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
			user_id      UUID NOT NULL,
			content      TEXT NOT NULL DEFAULT '',
			type         VARCHAR(50) NOT NULL DEFAULT 'text',
			media_url    TEXT NOT NULL DEFAULT '',
			is_edited    BOOLEAN NOT NULL DEFAULT FALSE,
			is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
			edit_history JSONB NOT NULL DEFAULT '[]',
			created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
		);
		CREATE INDEX IF NOT EXISTS idx_messages_room_created
			ON messages (room_id, created_at DESC);
		CREATE INDEX IF NOT EXISTS idx_messages_user
			ON messages (user_id);

		-- Media lives independently of messages — prevents broken refs on message delete
		CREATE TABLE IF NOT EXISTS media_library (
			id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
			uploader_id       UUID NOT NULL,
			filename          TEXT NOT NULL,
			original_filename TEXT NOT NULL DEFAULT '',
			mime_type         TEXT NOT NULL,
			size              BIGINT NOT NULL DEFAULT 0,
			url               TEXT NOT NULL,
			sha256            TEXT NOT NULL DEFAULT '',
			created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
		);
		CREATE INDEX IF NOT EXISTS idx_media_library_uploader
			ON media_library (uploader_id);

		-- Read receipts table (written async from Redis)
		CREATE TABLE IF NOT EXISTS message_reads (
			user_id         UUID NOT NULL,
			room_id         UUID NOT NULL,
			last_message_id UUID,
			updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
			PRIMARY KEY (user_id, room_id)
		);
	`)

	// ClickHouse (optional — analytics only)
	var chConn clickhouse.Conn
	if chDSN := getEnv("CLICKHOUSE_DSN", ""); chDSN != "" {
		chConn, err = clickhouse.Open(&clickhouse.Options{
			Addr: []string{getEnv("CLICKHOUSE_ADDR", "localhost:9000")},
			Auth: clickhouse.Auth{
				Database: "chat_history",
				Username: getEnv("CLICKHOUSE_USER", "clickhouse_user"),
				Password: getEnv("CLICKHOUSE_PASSWORD", "clickhouse_password"),
			},
			DialTimeout:     10 * time.Second,
			MaxOpenConns:    10,
			MaxIdleConns:    5,
			ConnMaxLifetime: time.Hour,
		})
		if err != nil {
			log.Printf("ClickHouse connect warning: %v", err)
			chConn = nil
		} else {
			chConn.Exec(ctx, `
				CREATE TABLE IF NOT EXISTS chat_messages (
					id         UUID,
					room_id    UUID,
					user_id    UUID,
					content    String,
					type       String,
					media_url  String,
					created_at DateTime64(3)
				) ENGINE = MergeTree()
				ORDER BY (room_id, created_at)
			`)
		}
	}

	// Media storage directory
	mediaDir := getEnv("MEDIA_STORAGE_DIR", "./media")
	if err := os.MkdirAll(mediaDir, 0755); err != nil {
		log.Fatalf("Failed to create media storage dir: %v", err)
	}
	// MEDIA_BASE_URL must be the public-facing path that browser clients use to fetch media.
	// In production this is the gateway path (/api/v1/chat/media) so all traffic stays on
	// the same host:port. Override via env var if a CDN or separate object-storage URL is used.
	mediaBaseURL := getEnv("MEDIA_BASE_URL", "/api/v1/chat/media")

	srv := &Server{
		db:              pool,
		rdb:             rdb,
		ch:              chConn,
		centrifugoURL:   getEnv("CENTRIFUGO_URL", "http://localhost:8000"),
		centrifugoKey:   getEnv("CENTRIFUGO_API_KEY", "centrifugo_api_key"),
		mediaStorageDir: mediaDir,
		mediaBaseURL:    mediaBaseURL,
	}

	// Background goroutine: flush read receipts from Redis → PostgreSQL every 10 s
	go srv.flushReadReceiptsToPostgres(ctx)

	r := mux.NewRouter()
	r.HandleFunc("/health", srv.Health).Methods(http.MethodGet)
	r.HandleFunc("/rooms", srv.CreateRoom).Methods(http.MethodPost)
	r.HandleFunc("/rooms/{roomId}", srv.GetRoom).Methods(http.MethodGet)
	r.HandleFunc("/rooms/{roomId}/join", srv.JoinRoom).Methods(http.MethodPost)
	r.HandleFunc("/rooms/{roomId}/invite", srv.InviteParticipant).Methods(http.MethodPost)
	r.HandleFunc("/rooms/{roomId}/messages", srv.SendMessage).Methods(http.MethodPost)
	r.HandleFunc("/rooms/{roomId}/messages/{messageId}", srv.GetMessage).Methods(http.MethodGet)
	r.HandleFunc("/rooms/{roomId}/messages/{messageId}", srv.EditMessage).Methods(http.MethodPatch)
	r.HandleFunc("/rooms/{roomId}/messages/{messageId}", srv.DeleteMessage).Methods(http.MethodDelete)
	r.HandleFunc("/rooms/{roomId}/read", srv.MarkRead).Methods(http.MethodPost)
	r.HandleFunc("/rooms/{roomId}/history", srv.GetHistory).Methods(http.MethodGet)
	r.HandleFunc("/media/upload", srv.UploadMedia).Methods(http.MethodPost)
	r.HandleFunc("/media/{filename}", srv.ServeMedia).Methods(http.MethodGet)

	port := getEnv("PORT", "4004")
	server := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
	}

	log.Printf("Chat service starting on :%s", port)
	if err := server.ListenAndServe(); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
