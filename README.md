# Splitwise Firefly Sync

This tool syncs the expenses from [Splitwise](https://www.splitwise.com) to [Firefly III](https://www.firefly-iii.org) using their respective APIs.

This is designed to be run as a cron job to sync the past `n` days' transactions.

## Environment Variables

Set these variables either in the environment or a `.env` file along with the script. For docker, the location would be `/app/.env`.

1. `SPLITWISE_TOKEN`: Get the token after [registering your app](https://secure.splitwise.com/apps) as mentioned in their [docs](https://dev.splitwise.com/#section/Authentication).
2. `FIREFLY_URL=http://firefly:8080`: Set your Firefly III instance URL.
3. `FIREFLY_TOKEN`: Set your Firefly III Personal Access Token as shown in their [docs](https://docs.firefly-iii.org/firefly-iii/api/#authentication).
4. `FIREFLY_DEFAULT_SPEND_ACCOUNT=Amex`: Set the default source account to use when you paid for the expense in Splitwise.
5. `FIREFLY_DEFAULT_TRXFR_ACCOUNT=Chase`: Set the default source account to use when someone else paid for the expense in Splitwise.
6. `FIREFLY_DEFAULT_CATEGORY`: Set the default category to use. If empty, falls back to the Splitwise category.
7. `FIREFLY_DRY_RUN`: Set this to any value to dry run and skip the firefly API call.
8. `SPLITWISE_DAYS=1`

## Note/Comment format

Enter a note or a comment in the below format on Splitwise:

`Firefly[/destination-account][/category][/source-account][/description]`

If the destination account is not provided, the expense title will be used, which may create a new expense account on Firefly. The next two use their respective defaults from environment variables. Description, if provided, overrides the Splitwise description. Only the user's comments will be considered, not anyone else. If you update the transaction in any way after someone entered a note (not comment) that matches, it will be considered. Priority is for the latest comment > old comment > notes.

## Issues

See [issues](issues) for current drawbacks in the implementation.
