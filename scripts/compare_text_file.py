import filecmp
import sys
import os



def main():
    if not os.path.exists(sys.argv[1]):
        print("File %s does not exist" % sys.argv[1])
        sys.exit(1)
    if not os.path.exists(sys.argv[2]):
        print("File %s does not exist" % sys.argv[2])
        sys.exit(1)

    f = [os.path.abspath(sys.argv[i+1]) for i in range(2)]


    return filecmp.cmp(f[0], f[1], shallow=False)

if __name__ == '__main__':
    print (main())
    sys.exit(0)