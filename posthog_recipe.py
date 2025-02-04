import marimo

__generated_with = "0.10.17"
app = marimo.App(width="medium")


@app.cell
def _():
    from cosmic.connectors import PostHogService
    from datetime import datetime, timezone, timedelta
    import io
    import base64
    import csv
    import resend


    def initialize_posthog(api_key: str, project_id: str):
        credentials = {
            "api_key": api_key,
            "base_url": "https://us.posthog.com",
            "project_id": project_id,
        }
        posthog_service = PostHogService(credentials)
        return posthog_service
    return (
        PostHogService,
        base64,
        csv,
        datetime,
        initialize_posthog,
        io,
        resend,
        timedelta,
        timezone,
    )


@app.cell
def _():
    # TODO: Make the date configurable as now() - 3.days
    def get_posthog_results(start_date, posthog_service):
        res = posthog_service.fetch_posthog_user_logins(start_date)
        column_types = res["data"]["types"]
        results = res["data"]["results"]

        return results
    return (get_posthog_results,)


@app.cell
def _(datetime, timezone):
    def get_posthog_churn_data(events):
        # Get uniuqe user_ids
        all_user_ids = set()
        churn_data = []

        for row in events:
            user_id = row[1]  # distinct id
            # print("user_id", user_id)
            date = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            days_ago = (now - date).days

            if user_id not in all_user_ids:
                churn_data.append(
                    {"user_id": user_id, "days_logged_in_ago": days_ago}
                )
                all_user_ids.add(user_id)
        print(churn_data)
        return churn_data
    return (get_posthog_churn_data,)


@app.cell
def _(base64, csv, datetime, io, resend):
    def send_email(churn_data):
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=churn_data[0].keys())
        writer.writeheader()  # Write header
        writer.writerows(churn_data)
        date = datetime.now()
        formatted_date = date.strftime("%b, %d, %Y")
        subject = f"Cosmic update {formatted_date}: Users last logged in"

        # Get the CSV content as string
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()

        # Encode the CSV content to Base64 for email attachement
        encoded_csv = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")

        resend.api_key = ""

        # Sending email with the attachement
        r = resend.Emails.send(
            {
                "from": "shikhar@agentkali.ai",
                "to": ["shikharsakhuja@gmail.com", "charlesjavelona@gmail.com"],
                "subject": subject,
                "html": "<p>Hi team, please see our users last login date.</p>",
                "attachments": [
                    {
                        "filename": f"provision-churn-trigger-{formatted_date}.csv",
                        "content": encoded_csv,
                        "content_type": "text/csv",
                    }
                ],
            }
        )
        print("Sending email", r)
    return (send_email,)


@app.cell
def _(get_posthog_churn_data, get_posthog_results, initialize_posthog):
    from pydantic import BaseModel


    class EntrypointParams(BaseModel):
        date: str
        api_key: str
        project_id: str


    def entrypoint(params: EntrypointParams):
        posthog_service = initialize_posthog(params.api_key, params.project_id)
        date_three_months_ago = params.date
        posthog_results = get_posthog_results(
            date_three_months_ago, posthog_service
        )
        churn_data = get_posthog_churn_data(posthog_results)
        # send_email(churn_data)
    return BaseModel, EntrypointParams, entrypoint


@app.cell
def _(EntrypointParams, datetime, entrypoint, timedelta, timezone):
    start_date = str((datetime.now(timezone.utc) - timedelta(days=90)).date())
    api_key = ""
    project_id = ""
    params = EntrypointParams(
        date=start_date, api_key=api_key, project_id=project_id
    )
    print(entrypoint(params))
    return api_key, params, project_id, start_date


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
