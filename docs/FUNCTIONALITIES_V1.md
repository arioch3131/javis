# Functionalities V1

This document summarizes the main application features available in V1 of `Javis`. It describes user-facing behavior without going into full implementation details.

## 1. Content Scanning

The application can scan a local folder to detect files to index.

Main capabilities:

- start a quick scan by opening a folder;
- start an advanced scan with configuration;
- select file groups to process: documents, images, videos, audio, others;
- support extensions configured in settings;
- display operation progress and status;
- cancel a running scan.

Expected result:

- discovered files are added to the database;
- a file hash can be computed for duplicate detection;
- the results list is refreshed in the interface;
- additional processing steps can be chained during scan.

## 2. Thumbnail Generation and Metadata Extraction

During or after scan, the application can enrich files with two complementary processes:

- `thumbnails`: generate thumbnails for visual display;
- `metadata`: extract technical and document information.

Examples of managed data:

- file size;
- dates;
- dimensions;
- format;
- file hash;
- year inferred from metadata or filesystem.

Functional impact:

- richer display in grid, list, and preview views;
- better input for sorting, filtering, categorization, and organization.

## 3. Duplicate Detection via Hash

The application can detect logical duplicates using the file hash stored in database.

Main capabilities:

- compute and store a content hash during indexing/update;
- group files sharing the same hash;
- expose duplicate count in content data;
- reuse this information in business workflows.

Functional use cases:

- identify files with identical content even if filenames differ;
- simplify library analysis before organization;
- reduce unnecessary processing on already known files.

In V1, this detection is notably used to support categorization:

- if a file shares the same hash as an already categorized file;
- the existing category can be reused to avoid a new LLM call.

## 4. Automatic Categorization

The application can categorize files automatically through the LLM layer.

Main capabilities:

- categorize from current view;
- configure available categories;
- support images and documents;
- preview mode or full processing mode;
- confidence threshold;
- option to process only uncategorized files;
- save results in database.

Expected result:

- each file can receive a category;
- confidence and extraction details are stored;
- duplicates detected by hash can reuse existing categorization;
- categories can then be used in filtering and organization.

## 5. Automatic Organization

The application can reorganize files using multiple strategies.

Main capabilities:

- select a target folder;
- `copy` mode or other action depending on configuration;
- organize by category;
- organize by year;
- organize by file type;
- combined strategies, for example category/year or type/category;
- preview mode before execution;
- progress tracking during operation.

Expected result:

- creation of a coherent target tree;
- file move/copy according to selected strategy;
- final summary of processed, successful, and failed files.

### V1 Warning on `move` Mode

For V1, `copy` should be considered the recommended mode.

`move` exists, but should not yet be treated as a fully reliable consolidation flow without additional checks. In particular, attention is required for synchronization between physical file move and database state.

In practice:

- `copy` is suitable for consolidating a library without risking source loss;
- `move` should be hardened in V2 to become the normal mode for redundancy cleanup and final consolidation into a single tree.

## 6. Results Filtering

Users can refine displayed results in the interface without re-running a scan.

Available filters:

- file type;
- category;
- year;
- extension.

Related capabilities:

- combine multiple filters;
- reset filters;
- immediate update of visible list;
- consistency between current view and subsequent operations.

Expected use:

- quickly isolate a subset of files;
- run categorization or organization on the already filtered view.

## 7. Configuration and Settings

The application provides a centralized configuration screen.

Notable functional settings:

- language;
- theme;
- API URL;
- timeouts and retries;
- image and document LLM models;
- prompts;
- scan extensions;
- categories;
- confidence threshold;
- parameters related to thumbnails and preprocessing.

Expected result:

- settings are persistent;
- application components reload them without duplicating config logic;
- configuration directly controls scan and categorization behavior.

## 8. Image / File Details

The application provides a detail view for selected files.

Main capabilities:

- open a details dialog from results views;
- show a file-adapted preview;
- display associated file information;
- navigate to previous/next file;
- keyboard left/right navigation in the details dialog.

This is important in V1 because it enables fast visual checks without leaving the main workflow.

## 9. View Navigation

The interface provides multiple result navigation modes.

Available modes:

- grid view;
- list view;
- column view.

Related navigation features:

- switch display mode;
- text search;
- result sorting;
- grid zoom;
- file selection;
- file activation to open details.

Goal:

- allow users to move from visual navigation to more tabular navigation depending on context.

## 10. Functional Pipeline Summary

The main V1 usage pipeline is:

```text
Scan -> enrich (metadata + thumbnails) -> navigate -> filter
-> categorize -> organize
```

Settings control this pipeline at multiple levels:

- what is scanned;
- how files are interpreted;
- how categorization is performed;
- how final organization is built.
