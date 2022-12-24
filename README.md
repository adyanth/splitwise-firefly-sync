# Splitwise Firefly Sync

This tool syncs the expenses from [Splitwise](https://www.splitwise.com) to [Firefly III](https://www.firefly-iii.org) using their respective APIs.

## Environment Variables

1. `SPLITWISE_TOKEN`: Set this variable either in the environment or /app/.env file. Get the token after [registering your app](https://secure.splitwise.com/apps) as mentioned in their [docs](https://dev.splitwise.com/#section/Authentication).
2. `FIREFLY_URL=http://firefly:8080`: Set your Firefly III instance URL.
3. `FIREFLY_TOKEN`: Set your Firefly III Personal Access Token as shown in their [docs](https://docs.firefly-iii.org/firefly-iii/api/#authentication).
4. `FIREFLY_DEFAULT_SPEND_ACCOUNT=Amex`: Set the default source account to use when you paid for the expense in Splitwise.
5. `FIREFLY_DEFAULT_TRXFR_ACCOUNT=Chase`: Set the default source account to use when someone else paid for the expense in Splitwise.
6. `FIREFLY_DEFAULT_CATEGORY`: Set the default category to use. If empty, falls back to the Splitwise category.
7. `FIREFLY_DRY_RUN`: Set this to any value to dry run and skip the firefly API call.

## Note/Comment format

Enter a note or a comment in the format `Firefly[/destination-account][/category][/source-account]`. If the destination account is not provided, the expense title will be used, which may create a new expense account on Firefly. The other two use their respective defaults from environment variables. Only the user's comments will be considered, not anyone else. If you update the transaction in any way after someone entered a note (not comment) that matches, it will be considered. Priority is latest comment > old comment > notes.

## Caveats

If multiple people including you paid for the expense on Splitwise, the spending account will be considered. If not, the transfer account will be considered.
