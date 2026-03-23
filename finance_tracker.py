import os

FILE_NAME = "transactions.txt"


def add_transaction():
    print("\n--- Add Transaction ---")
    t_type = input("Type (income/expense): ").lower()
    amount = float(input("Amount: "))
    category = input("Category: ")

    with open(FILE_NAME, "a") as file:
        file.write(f"{t_type},{amount},{category}\n")

    print("✅ Transaction recorded!")


def view_transactions():
    if not os.path.exists(FILE_NAME):
        print("No transactions found.")
        return

    print("\n--- Transactions ---")
    with open(FILE_NAME, "r") as file:
        for line in file:
            t_type, amount, category = line.strip().split(",")
            print(f"{t_type.upper()} | {amount} | {category}")


def calculate_balance():
    income = 0
    expenses = 0

    if not os.path.exists(FILE_NAME):
        print("No data available.")
        return

    with open(FILE_NAME, "r") as file:
        for line in file:
            t_type, amount, _ = line.strip().split(",")
            amount = float(amount)

            if t_type == "income":
                income += amount
            else:
                expenses += amount

    print("\n--- Summary ---")
    print(f"Total Income: {income}")
    print(f"Total Expenses: {expenses}")
    print(f"Balance: {income - expenses}")


def menu():
    while True:
        print("\n=== FinTech Expense Tracker ===")
        print("1. Add Transaction")
        print("2. View Transactions")
        print("3. View Summary")
        print("4. Exit")

        choice = input("Choose an option: ")

        if choice == "1":
            add_transaction()
        elif choice == "2":
            view_transactions()
        elif choice == "3":
            calculate_balance()
        elif choice == "4":
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    menu()
