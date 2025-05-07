def floyds(n):
    num, iters = 1, 1

    for _ in range(n):
        for __ in range(iters):
            print(num,end=" ")
            num += 1
        iters += 1
        print( )

floyds(4)





def easy_sort(arr):
    min = 9999
    for i in range(len(arr)):
        min = i
        for j in range(i, len(arr)):
            if arr[j] < arr[min]:
                min = j

        temp = arr[i]
        arr[i] = arr[min]
        arr[min] = temp
    return arr
print(easy_sort([90,1,5,200,3,23993]))