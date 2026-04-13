-- Migration: 003_voting_race_condition_fix
-- Adds denormalized vote_count to candidates to avoid N+1 AVG queries.
-- The vote_count is maintained by a DB trigger on the votes table.

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS vote_count INT NOT NULL DEFAULT 0;

-- Backfill existing counts
UPDATE candidates c
SET vote_count = (
    SELECT COUNT(*) FROM votes v WHERE v.candidate_id = c.id
);

-- Trigger: increment/decrement vote_count when a vote row is inserted/deleted/updated
CREATE OR REPLACE FUNCTION maintain_candidate_vote_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE candidates SET vote_count = vote_count + 1 WHERE id = NEW.candidate_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE candidates SET vote_count = GREATEST(vote_count - 1, 0) WHERE id = OLD.candidate_id;
    ELSIF TG_OP = 'UPDATE' AND OLD.candidate_id IS DISTINCT FROM NEW.candidate_id THEN
        -- Vote changed to a different candidate
        UPDATE candidates SET vote_count = GREATEST(vote_count - 1, 0) WHERE id = OLD.candidate_id;
        UPDATE candidates SET vote_count = vote_count + 1 WHERE id = NEW.candidate_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vote_count ON votes;
CREATE TRIGGER trg_vote_count
    AFTER INSERT OR UPDATE OF candidate_id OR DELETE ON votes
    FOR EACH ROW EXECUTE FUNCTION maintain_candidate_vote_count();

-- Index to efficiently query voted status per user per session (avoids N+1)
CREATE INDEX IF NOT EXISTS idx_votes_session_user
    ON votes (voting_session_id, user_id);
