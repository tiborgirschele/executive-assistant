-- Wir biegen die Quelle vorübergehend auf deinen Kalender um, 
-- damit du das Feature an dir selbst testen kannst.
UPDATE briefing_links 
SET source_person = 'tibor.girschele' 
WHERE target_person = 'tibor.girschele' AND rule_type = 'coach_event_append';
