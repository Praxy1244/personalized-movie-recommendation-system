# Check if reviews_list is a list or dictionary
if isinstance(reviews_list, list):
    print("reviews_list is a list.")
elif isinstance(reviews_list, dict):
    print("reviews_list is a dictionary.")
else:
    print("reviews_list is neither a list nor a dictionary.")
