# Agent TODOs

Address each item in a separate branch.

- [ ] **If-Match collision protection:** Capture the page's ETag when reading
  it and use `If-Match` when writing a toggled task. Handle a rejected
  conditional write without overwriting newer edits, and refresh the view.
  Account for the server not providing an ETag or supporting conditional
  writes.
- [ ] **Reduce full-screen refresh frequency:** Investigate the e-paper
  display's refresh behavior and reduce unnecessary full-screen refreshes
  while keeping displayed information current.
- [ ] **Display style improvements:** Improve the readability and visual
  presentation of pages, tasks, selection, and status messages on the e-paper
  display.
