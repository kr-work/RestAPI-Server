DO $$
BEGIN
    -- Drop the existing trigger if it exists
    IF EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'state_update_trigger'
    ) THEN
        DROP TRIGGER state_update_trigger ON state;
    END IF;

    -- Drop the existing function if it exists
    IF EXISTS (
        SELECT 1
        FROM pg_proc
        WHERE proname = 'notify_state_update'
    ) THEN
        DROP FUNCTION notify_state_update();
    END IF;
END;
$$;

-- Create the function
CREATE OR REPLACE FUNCTION notify_state_update()
RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('state_update', NEW.match_id::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger
CREATE TRIGGER state_update_trigger
AFTER INSERT ON state
FOR EACH ROW
EXECUTE FUNCTION notify_state_update();