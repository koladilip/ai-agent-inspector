# ui Specification

## Purpose

Provide a simple, responsive web interface for viewing agent execution traces with a timeline visualization, run listing, and detailed inspection panels. The UI must be lightweight (using FastAPI templates and HTMX or vanilla JS) and provide immediate value for debugging agent behavior.

## Requirements

### Requirement: Page layout

The system SHALL provide a three-panel layout: run list, timeline, and details.

#### Scenario: Default layout structure

- GIVEN the UI is loaded
- WHEN the page renders
- THEN the layout SHALL contain:
  - Left panel (30% width): Run list with filters
  - Center panel (45% width): Timeline visualization
  - Right panel (25% width): Detail view
- AND the layout SHALL be responsive
- AND on mobile, panels SHALL stack vertically

#### Scenario: Collapsible panels

- GIVEN the three-panel layout is displayed
- WHEN a user clicks the collapse button on a panel
- THEN that panel SHALL collapse to a thin strip
- AND the other panels SHALL expand to fill available space
- AND collapsed state SHALL persist in localStorage

#### Scenario: Panel resize

- GIVEN the layout is displayed
- WHEN a user drags the divider between panels
- THEN panels SHALL resize dynamically
- AND the new sizes SHALL be saved to localStorage
- AND minimum panel width SHALL be 200px

### Requirement: Run list panel

The system SHALL display a list of agent runs with filtering and search capabilities.

#### Scenario: Display run list

- GIVEN the API returns a list of runs
- WHEN the run list is rendered
- THEN each run SHALL display:
  - Run name
  - Status indicator (running: blue, completed: green, failed: red)
  - Start timestamp (relative time like "2 hours ago")
  - Duration
  - Step count badge
- AND runs SHALL be ordered newest first

#### Scenario: Status filtering

- GIVEN the run list is displayed
- WHEN a user clicks the "Failed only" filter button
- THEN only runs with status 'failed' SHALL be displayed
- AND the filter SHALL be active (visually highlighted)
- AND clicking again SHALL toggle the filter off

#### Scenario: Name search

- GIVEN the run list is displayed
- WHEN a user types in the search box
- THEN the list SHALL filter to matching run names
- AND the search SHALL be case-insensitive
- AND the search SHALL update as the user types (debounced to 300ms)

#### Scenario: Select a run

- GIVEN the run list is displayed
- WHEN a user clicks on a run
- THEN the run SHALL be highlighted as selected
- AND the timeline panel SHALL update to show this run's timeline
- AND the detail panel SHALL clear
- AND the selection SHALL persist across page refreshes

#### Scenario: Loading state

- GIVEN a user filters or searches
- WHEN data is being fetched
- THEN a loading spinner SHALL be displayed
- AND the UI SHALL remain interactive
- AND previous data SHALL remain visible until new data arrives

#### Scenario: Empty state

- GIVEN no runs match the current filters
- WHEN the run list renders
- THEN a message SHALL be displayed: "No runs found"
- AND suggestions SHALL be provided to adjust filters

### Requirement: Timeline panel

The system SHALL display a vertical timeline of events in the selected run.

#### Scenario: Render timeline

- GIVEN a run is selected with multiple steps
- WHEN the timeline renders
- THEN events SHALL be displayed vertically with arrows connecting them
- AND each event SHALL show:
  - Event type icon (LLM, tool, memory, error)
  - Event name (e.g., "web_search", "gpt-4")
  - Duration badge
  - Timestamp
  - Status indicator
- AND events SHALL be ordered top-to-bottom chronologically

#### Scenario: Event type icons

- GIVEN the timeline is rendered
- WHEN different event types are displayed
- THEN LLM calls SHALL use a brain/circuit icon
- AND tool calls SHALL use a wrench/tool icon
- AND memory operations SHALL use a database/memory icon
- AND errors SHALL use a warning/error icon
- AND final answers SHALL use a checkmark/star icon

#### Scenario: Timeline hover states

- GIVEN the timeline is rendered
- WHEN a user hovers over an event
- THEN the event SHALL be highlighted
- AND a tooltip SHALL show the event duration
- AND the event SHALL become clickable

#### Scenario: Click event for details

- GIVEN the timeline is displayed
- WHEN a user clicks on an event
- THEN the event SHALL be highlighted as active
- AND the detail panel SHALL populate with the event details
- AND the active state SHALL be visible

#### Scenario: Timeline filtering

- GIVEN a run has many events
- WHEN filter buttons are available (LLM only, Tools only, Errors only)
- AND a user clicks "Tools only"
- THEN only tool_call events SHALL be displayed in the timeline
- AND the filter SHALL be active
- AND clicking the filter again SHALL show all events

#### Scenario: Error highlighting

- GIVEN a run contains error events
- WHEN the timeline is displayed
- THEN error events SHALL be prominently highlighted in red
- AND error events SHALL pulse to draw attention
- AND the path to the error SHALL be highlighted

#### Scenario: Nested events

- GIVEN a run has nested operations (e.g., LLM calling a tool)
- WHEN the timeline is displayed
- THEN the tool event SHALL be indented under the LLM event
- AND a connecting line SHALL show the relationship
- AND the parent event SHALL be expandable/collapsible

#### Scenario: Timeline zoom

- GIVEN a run has many events
- WHEN a user adjusts a zoom slider
- THEN event spacing SHALL expand or contract
- AND more detail SHALL be visible at higher zoom levels
- AND more events SHALL fit at lower zoom levels

### Requirement: Detail panel

The system SHALL display detailed information about the selected event.

#### Scenario: Display event details

- GIVEN an event is selected in the timeline
- WHEN the detail panel renders
- THEN the following SHALL be displayed:
  - Event type and name
  - Full timestamp
  - Duration
  - Input section (expandable)
  - Output section (expandable)
  - Metadata section
- AND long content SHALL be truncated with "Show more" button

#### Scenario: Display LLM call details

- GIVEN an LLM call event is selected
- WHEN the detail panel renders
- THEN it SHALL show:
  - Model name
  - Prompt (with syntax highlighting for code blocks)
  - Response (with syntax highlighting)
  - Token usage (if available)
  - Temperature and other parameters

#### Scenario: Display tool call details

- GIVEN a tool call event is selected
- WHEN the detail panel renders
- THEN it SHALL show:
  - Tool name
  - Arguments (formatted as JSON)
  - Result (formatted as JSON)
  - Duration

#### Scenario: Display error details

- GIVEN an error event is selected
- WHEN the detail panel renders
- THEN it SHALL show:
  - Error message
  - Exception type
  - Stack trace (in a code block)
  - Context events leading to the error

#### Scenario: Display memory operation details

- GIVEN a memory read/write event is selected
- WHEN the detail panel renders
- THEN it SHALL show:
  - Memory key
  - Value (truncated if long)
  - Operation type (read/write)

#### Scenario: Copy to clipboard

- GIVEN the detail panel is showing event data
- WHEN a user clicks the "Copy" button
- THEN the displayed data SHALL be copied to clipboard
- AND a "Copied!" confirmation SHALL briefly appear

#### Scenario: JSON formatting

- GIVEN event data contains JSON
- WHEN the detail panel displays it
- THEN JSON SHALL be pretty-printed
- AND syntax highlighting SHALL be applied
- AND the JSON SHALL be collapsible by object/array

#### Scenario: No selection state

- GIVEN no event is selected
- WHEN the detail panel renders
- THEN it SHALL display "Select an event to view details"
- AND the panel SHALL show a helpful tip about using the timeline

### Requirement: Navigation and routing

The system SHALL support browser navigation and URL-based state.

#### Scenario: URL-based run selection

- GIVEN a user opens a URL like `/?run=abc-123`
- WHEN the page loads
- THEN the run with ID abc-123 SHALL be selected
- AND its timeline SHALL be displayed

#### Scenario: URL-based event selection

- GIVEN a user opens a URL like `/?run=abc-123&event=456`
- WHEN the page loads
- THEN the run abc-123 SHALL be selected
- AND event 456 SHALL be selected and shown in detail panel

#### Scenario: Update URL on selection

- GIVEN a user selects a run and event
- WHEN the selection is made
- THEN the URL SHALL update to include run and event IDs
- AND the page SHALL not reload (pushState)

#### Scenario: Browser back/forward

- GIVEN a user has navigated between multiple runs
- WHEN they click the browser back button
- THEN the previous selection SHALL be restored
- AND the UI SHALL update accordingly

### Requirement: Real-time updates

The system SHALL support real-time updates for running runs.

#### Scenario: Live timeline updates

- GIVEN a run is currently in progress (status: running)
- WHEN new events are emitted
- THEN the timeline SHALL update automatically
- AND new events SHALL appear at the bottom
- AND the timeline SHALL auto-scroll to show new events

#### Scenario: Live status updates

- GIVEN a run is displayed with status "running"
- WHEN the run completes
- THEN the status SHALL change to "completed" or "failed"
- AND the status indicator SHALL update color
- AND a notification SHALL appear

#### Scenario: Polling configuration

- GIVEN real-time updates are enabled
- WHEN the UI polls for updates
- THEN the polling interval SHALL be 2 seconds
- AND polling SHALL stop when the run is completed
- AND polling SHALL be configurable

### Requirement: Dark mode

The system SHALL support dark/light theme switching.

#### Scenario: Toggle dark mode

- GIVEN the UI is in light mode
- WHEN a user clicks the dark mode toggle
- THEN the theme SHALL switch to dark
- AND the preference SHALL be saved to localStorage

#### Scenario: Respect system preference

- GIVEN a user visits for the first time
- WHEN the page loads
- THEN the theme SHALL match the user's system preference
- AND the theme SHALL be set automatically

#### Scenario: Theme persistence

- GIVEN a user has set a theme preference
- WHEN they refresh the page
- THEN the saved theme SHALL be applied
- AND the UI shall not flash

### Requirement: Performance

The UI SHALL render quickly and handle large runs efficiently.

#### Scenario: Fast initial load

- GIVEN the UI is being accessed
- WHEN the page loads
- THEN the time to first paint SHALL be under 1 second
- AND the initial API response SHALL be under 500ms

#### Scenario: Handle large runs

- GIVEN a run has 1000+ steps
- WHEN the timeline is displayed
- THEN the UI SHALL render within 2 seconds
- AND only visible events SHALL be rendered (virtual scrolling)
- AND additional events SHALL load on scroll

#### Scenario: Debounce API calls

- GIVEN a user is typing in the search box
- WHEN they type multiple characters quickly
- THEN only one API call SHALL be made after typing stops
- AND the debounce delay SHALL be 300ms

### Requirement: Accessibility

The UI SHALL be accessible to all users.

#### Scenario: Keyboard navigation

- GIVEN the UI is displayed
- WHEN a user uses the keyboard
- THEN they SHALL be able to:
  - Tab between panels
  - Use arrow keys to navigate the run list
  - Use arrow keys to navigate the timeline
  - Press Enter to select
  - Press Escape to clear selection

#### Scenario: Screen reader support

- GIVEN a screen reader is being used
- WHEN the UI renders
- THEN all interactive elements SHALL have ARIA labels
- AND event status SHALL be announced (e.g., "Error event, web search tool call failed")
- AND focus states SHALL be clearly visible

#### Scenario: Color contrast

- GIVEN the UI is displayed
- WHEN color is used to convey information
- THEN the contrast ratio SHALL meet WCAG AA standards (4.5:1 for text)
- AND status SHALL be indicated by both color and icons

### Requirement: Error handling

The UI SHALL handle errors gracefully.

#### Scenario: API error display

- GIVEN an API request fails
- WHEN the error is caught
- THEN a non-intrusive toast notification SHALL appear
- AND the notification SHALL describe the error
- AND the notification SHALL include a "Retry" button
- AND the UI shall not break

#### Scenario: Network connectivity

- GIVEN the network connection is lost
- WHEN the UI attempts to fetch data
- THEN an offline indicator SHALL appear
- AND the UI shall use cached data if available
- AND the UI shall retry automatically when connectivity returns

#### Scenario: Invalid run ID

- GIVEN a user navigates to an invalid run ID
- WHEN the API returns 404
- THEN a clear error message SHALL be displayed
- AND the user SHALL be directed to the run list
- AND the URL SHALL be cleaned up

### Requirement: Responsive design

The UI SHALL work on various screen sizes.

#### Scenario: Mobile layout

- GIVEN the screen width is under 768px
- WHEN the UI renders
- THEN panels SHALL stack vertically
- AND the active panel SHALL be shown full-screen
- AND tabs SHALL appear at the top to switch between panels
- AND bottom navigation SHALL provide quick access

#### Scenario: Tablet layout

- GIVEN the screen width is between 768px and 1024px
- WHEN the UI renders
- THEN the layout SHALL be two columns
- AND the run list and timeline SHALL be side by side
- AND the detail panel SHALL be below the timeline

#### Scenario: Desktop layout

- GIVEN the screen width is over 1024px
- WHEN the UI renders
- THEN the full three-panel layout SHALL be displayed
- AND panels SHALL have the default widths (30%, 45%, 25%)

### Requirement: Data export

The UI SHALL support exporting trace data.

#### Scenario: Export run as JSON

- GIVEN a run is selected
- WHEN a user clicks "Export JSON"
- THEN the complete run data SHALL be downloaded as a JSON file
- AND the filename SHALL be `run-{run_id}-{timestamp}.json`
- AND all steps SHALL be included with full details

#### Scenario: Export timeline as image

- GIVEN a timeline is displayed
- WHEN a user clicks "Export Image"
- THEN the timeline SHALL be rendered as a PNG image
- AND the image SHALL include all visible events
- AND the image SHALL be downloaded

#### Scenario: Export run details

- GIVEN a run is selected
- WHEN a user clicks "Copy Run Details"
- THEN a formatted summary SHALL be copied to clipboard
- AND the summary SHALL include run name, status, duration, and key events