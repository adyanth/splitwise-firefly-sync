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
9. `SW_BALANCE_ACCOUNT=Splitwise balance`: Set this to the name of the virtual Splitwise balance asset account on Firefly to enable the debt tracking feature.

## Debt tracking feature
When enabled, tracks Splitwise payable and receivable debts in an account defined by `SW_BALANCE_ACCOUNT`.

For example, assume you paid 100$ but your share was only 40$. Splitwise records correctly that you are owed 60$ - so your total assets haven't really decreased by 100$, only by 40$. Enabling this feature correctly tracks this in Firefly, without compromising on recording the real 100$ transaction you will see in your bank statement.

For each Splitwise expense, create two Firefly transactions: 
1. A withdrawal from a real account, recording the real amount of money paid in the expense
2. A deposit to the `SW_BALANCE_ACCOUNT` equal the difference between the amount paid and the amount owed.

## Note/Comment format

Enter a note or a comment in the below format on Splitwise:

`Firefly[/destination-account][/category][/description][/source-account]`

If the destination account is not provided, the expense title will be used, which may create a new expense account on Firefly. The next two use their respective defaults from environment variables. Description, if provided, overrides the Splitwise description. Only the user's comments will be considered, not anyone else. If you update the transaction in any way after someone entered a note (not comment) that matches, it will be considered. Priority is for the latest comment > old comment > notes.

## Issues

See [issues](https://github.com/adyanth/splitwise-firefly-sync/issues) for 
current drawbacks in the implementation.
