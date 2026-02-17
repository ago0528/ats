## Prompt Modal Redesign Requirements (View/Edit Split + Monaco)

### Decisions

* 'View' and 'Edit' modal must be implemented as **separate modals** (no tabs).
* 'Edit' modal must use **Monaco Diff Editor**.

---

## 1) Fixed Modal Height + Internal Fill/Scroll (All Modals)

* Every modal must fit fully within the viewport (no off-screen modal content).
* Use a fixed modal height policy:

  * Modal container: `max-height: 80vh` (or equivalent), **modal container must not scroll**.
  * Layout: **Header (fixed) + Body (fill) + Footer (fixed)**.
* The editor/text area region must **fill** the modal body height.
* If content exceeds available height, scrolling must occur **inside the editor/text area**, not by expanding the editor height.

  * **Do not** set huge textarea heights (e.g., 2000px+).
  * Monaco internal scroll must handle overflow.

---

## 2) Split View vs Edit Modals + Edit Modal Diff UX

### 2.1 View/Edit separation

* View and Edit must be **separate modals** (not a shared modal with tabs).

### 2.2 Edit modal label + header adjustments

* Move the tag currently shown as “Length delta” (길이 차이) to be **inline on the same row, positioned to the right of the TO-BE title**.
* Rename titles:

  * “변경 전” → **AS-IS**
  * “현재” → **TO-BE**

### 2.3 Diff presentation (IDE-style)

* The Edit modal must provide a diff UI comparable to a code IDE:

  * **line numbers** on the left
  * clear visualization for **deleted**, **added**, and **modified** lines (gutter markers + highlight)
  * side-by-side diff view (AS-IS vs TO-BE)
* The diff must be easy to scan “at a glance” for changes.

---

## 3) View Modal: Remove “Current/TO-BE” Panel

* In the **View modal**, remove the “TO-BE/Current” area entirely.
* The View modal must not show a two-column comparison layout.

---

## 4) View Modal: Rename the Remaining Panel Title

* In the **View modal**, rename the remaining panel title (currently “변경 전”) to a View-appropriate label.
* Recommended label: **PROMPT** (or **CURRENT PROMPT**), but must be consistent across the app.

---

## 5) Non-editable Text Areas Must Look Disabled

* Any non-editable text area/editor must be visually **Disabled** (not just `readonly`) to make “cannot edit” obvious.

  * Applies to: AS-IS panel in Edit modal, and the View modal content.

---

## 6) Edit Modal Footer Buttons: Position + Ordering Rule

* In the Edit modal, **Save** and **Cancel** must be placed at the **bottom-right** of the modal (fixed footer; always visible).
* Button ordering rule (strict):

  * Cancel/Close-type buttons must always be the **leftmost** within the footer button group.
  * Save is the primary action to the right.

---

## Additional Requirements (Accepted)

### A) Change Summary

* Display change summary badges:

  * `+Added / -Removed / ~Modified` line counts.

### B) Copy Actions

* Provide:

  * **Copy AS-IS**
  * **Copy TO-BE**
  * **Copy DIFF**

### C) Reset Action

* Provide **Reset TO-BE to AS-IS** with a confirmation step.

### D) Unsaved Changes Protection

* If TO-BE has unsaved changes, closing via **X / ESC / overlay click** must show a confirmation dialog:

  * Discard changes / Keep editing.

### E) Modal Width Guidance

* View modal: `width: min(920px, 90vw)`
* Edit modal: `width: min(1120px, 90vw)`