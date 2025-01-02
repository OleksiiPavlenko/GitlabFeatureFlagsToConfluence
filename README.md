# GitlabFeatureFlagToConfluence
# Feature Flags Manager

**Feature Flags Manager** is a tool designed to streamline the management of feature flags in your projects. It automates the synchronization of feature states between your codebase and documentation in Confluence, enabling teams to easily track the status of features and ownership responsibilities.

## Why is this important?

In large projects, the number of active features can grow quickly, making it harder to keep track of them.  
**Feature Flags Manager** helps to:  
- Keep feature flag statuses consistent between repositories and documentation.  
- Avoid confusion about which team is responsible for each feature.  
- Automatically mark deleted features to preserve their history.  

This tool is particularly useful for:  
- **Developers**: To better understand which features are active.  
- **DevOps teams**: To simplify the process of updating feature flags.  
- **Product Managers**: To track feature progress and responsible teams.  

## How does it work?

1. **Automatic status updates**: The tool fetches feature flag data from GitLab and updates the table in Confluence.  
2. **Manual ownership updates**: Teams can add or modify ownership information without overwriting statuses.  
3. **Marking deleted features**: Deleted flags are marked with a "Deleted" status to avoid losing their history.  

## Use Case Example

**Scenario:** Your team adds a new feature and activates its flag in the code. You want to ensure that the flag’s status is reflected in Confluence, and the responsible team is aware of it.  

1. Run the `Feature Flags Manager` script.  
2. The table in Confluence is automatically updated with the latest statuses.  
3. Your team adds its name to the corresponding row in the table.  

**Result:** You always have up-to-date information about feature statuses and their ownership.  

## Visualization

![Screenshot of the table in Confluence](link_to_screenshot)

## Getting Started

1. Follow the [Installation Instructions](#installation).  
2. Run the script using:  
   ```bash
   python main.py

## Technical Overview

### How It Works

The **Feature Flags Manager** integrates with GitLab and Confluence APIs to synchronize feature flag statuses and ownership information. Below is a high-level overview of its workflow:  

1. **Fetching Data**:  
   - The script connects to GitLab using its API.  
   - It retrieves the list of active and deleted feature flags from the specified project repositories.  

2. **Processing Data**:  
   - The fetched flags are compared with the existing data in Confluence.  
   - Updates are identified for flags that have changed status, ensuring accuracy.  

3. **Updating Confluence**:  
   - The tool interacts with the Confluence API to update the feature flags table.  
   - If a feature is deleted, the tool marks its status as "Deleted" but retains its history.  
   - Ownership data added manually by teams remains untouched.  

4. **Error Handling**:  
   - The script handles API connection failures, invalid credentials, and other runtime exceptions gracefully, ensuring reliability.

### Key Components

- **GitLab API Integration**:  
  Uses the GitLab REST API to fetch feature flag data. This requires:  
  - A personal access token with `read_api` permissions.  
  - The GitLab project ID(s) to monitor.  

- **Confluence API Integration**:  
  Updates and modifies the feature flags table in Confluence. This requires:  
  - An Atlassian account with permissions to edit pages in the specified Confluence space.  
  - The ID of the Confluence page containing the feature flags table.  

- **Data Mapping**:  
  Each feature flag is mapped by its unique identifier (key) to ensure updates are applied to the correct rows in the table.  

### Installation and Configuration

1. **Setup API Tokens**:  
   - Create a `.env` file in the project directory:  
     ```plaintext
     GITLAB_TOKEN=your_gitlab_personal_access_token
     CONFLUENCE_USER=your_email@example.com
     CONFLUENCE_API_TOKEN=your_confluence_api_token
     CONFLUENCE_SPACE=TS
     CONFLUENCE_PAGE_ID=123456789
     ```

2. **Install Dependencies**:  
   - Ensure Python 3.x is installed.  
   - Install required libraries using `pip`:  
     ```bash
     pip install -r requirements.txt
     ```  

3. **Run the Script**:  
   Execute the main script to perform a synchronization:  
   ```bash
   python main.py

Key Functions
Logging
add_to_log(message): Logs activity for debugging and monitoring.
Feature Flag Retrieval
fetch_all_feature_flags(repo_id): Fetches all flags from a GitLab repository.
Handles pagination to retrieve complete datasets.
Team Assignment
get_team_from_flag_name(flag_name): Associates a flag with a team based on its name.
Data Consolidation
merge_feature_flags():
Combines feature flags from all repositories.
Adds ownership details and updates the status (e.g., Active, Inactive, Deleted).
Confluence Integration
fetch_existing_table_from_confluence(page_title): Retrieves an existing table from a Confluence page.
update_table(existing_table, new_table): Merges new data into the existing Confluence table.
upload_table_to_confluence(html_content, page_id): Updates or creates a Confluence page with the consolidated table.
HTML Generation
generate_html_with_icons_and_dropdown(table):
Converts the consolidated table to HTML.
Adds status icons and dropdowns for detailed flag information.
3. Process Flow
Retrieve Feature Flags:

Fetch all flags from repositories defined in REPOSITORY_MAP.
Determine team ownership based on flag names.
Consolidate Data:

Merge new data with existing records.
Mark deleted flags without removing historical details.
Upload to Confluence:

Fetch the current Confluence table.
Update the table with new data or create a new page.
Generate Enhanced HTML:

Include icons and dropdowns for improved visualization.
4. Output Example
The table includes:

Feature Name: Name of the feature flag.
Description: Detailed description (if available).
Ownership: Team or user responsible for the flag.
Status: Current status (Active 🟢, Inactive ⚪, Deleted 🔴).
Repository Details: Expandable dropdowns for flag-specific data.
5. Confluence Page Structure
Page Title: Feature Flag Dashboard
Columns:
Feature toggle name
Feature description
Owned by
Status
Repository-specific columns with status and detailed information.

