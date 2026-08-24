-- Bridge-authoritative TimelineBundle/project-data lane.
-- Legacy rows are deliberately represented as JSON null: absent bundle and
-- explicit clear have one durable read shape while the HTTP request still
-- distinguishes omitted (preserve) from null (clear).
ALTER TABLE timelines
  ADD COLUMN project_data_json TEXT NOT NULL DEFAULT 'null'
  CHECK (json_valid(project_data_json));
