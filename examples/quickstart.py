import cityhash

assert cityhash.CityHash64(b"hello") == 13009744463427800296
assert cityhash.CityHash32("hello") == 2039911270

seeded = cityhash.CityHash128WithSeed(
    b"cityhash in Mojo",
    0x0123456789ABCDEFFEDCBA9876543210,
)
print(seeded)
