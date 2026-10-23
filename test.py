"""a, b, c, d = int(input()), int(input()), int(input()), int(input())
if min(a, b) + max(c, d) >= min(c, d) + max(a, b):
    print(min(a, b) + max(c, d))
else:
    print(min(c, d) + max(a, b))"""
"""vh = input()
#Если интересно почему я назвал именно vh, то потому что это входные данные :)
if not len(vh) % 2:
    print(len(vh))
    f_sl = vh[:len(vh) // 2]
    s_sl = vh[len(vh) // 2:]
else:
    f_sl = vh[:len(vh) // 2]
    s_sl = vh[len(vh) // 2 + 1:]
    print(f_sl, s_sl)

s_sl = s_sl[::-1]
for i in range(len(f_sl)):
    if f_sl[i] != s_sl[i]:
        print(i + 1, int(len(vh) / 2 + i + 1.5))
        break"""
"""vh = input()
#Если интересно почему я назвал именно vh, то потому что это входные данные :)
f_sl = vh[:len(vh) // 2]
s_sl = vh[len(vh) // 2:]
s_sl = s_sl[::-1]
idx = -1
for i in range(len(f_sl)):
    if f_sl[i] != s_sl[i]:
        idx = i
        break
if idx == -1:
    for i in range(len(vh)):
        for ii in range(i + 1, len(vh)):
            if vh[i] == vh[ii]:
                print(i + 1, ii + 1)
                exit()
else:
    for i in range(idx + 1, len(vh)):
        if vh[i] == s_sl[idx]:
            vh_list = list(vh)
            vh_list[idx], vh_list[i] = vh_list[i], vh_list[idx]
            if vh_list == vh_list[::-1]:
                print(idx + 1, i + 1)
                break
    for i in range(len(vh) - 1 - idx):
        if vh[i] == f_sl[idx]:
            vh_list = list(vh)
            vh_list[len(vh) - 1 - idx], vh_list[i] = vh_list[i], vh_list[len(vh) - 1 - idx]
            if vh_list == vh_list[::-1]:
                print(len(vh) - idx, i + 1)
                break"""
"""vh = input()
#Если интересно почему я назвал именно vh, то потому что это входные данные :)
f_sl = vh[:len(vh) // 2]
s_sl = vh[len(vh) // 2:]
s_sl = s_sl[::-1]
idx = -1
for i in range(len(f_sl)):
    if f_sl[i] != s_sl[i]:
        idx = i
        break

if idx == -1:
    for i in range(len(vh)):
        for ii in range(i + 1, len(vh)):
            if vh[i] == vh[ii]:
                print(i + 1, ii + 1)
                exit()
else:
    for i in range(idx + 1, len(vh)):
        if vh[i] == s_sl[idx]:
            vh_list = list(vh)
            vh_list[idx], vh_list[i] = vh_list[i], vh_list[idx]
            if vh_list == vh_list[::-1]:
                print(idx + 1, i + 1)
                exit()
                
    for i in range(len(vh) - 1 - idx):
        if vh[i] == f_sl[idx]:
            vh_list = list(vh)
            vh_list[len(vh) - 1 - idx], vh_list[i] = vh_list[i], vh_list[len(vh) - 1 - idx]
            if vh_list == vh_list[::-1]:
                print(len(vh) - idx, i + 1)
                exit()"""
