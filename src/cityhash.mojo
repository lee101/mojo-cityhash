from std.bit import rotate_bits_right


comptime BytePtr = UnsafePointer[UInt8, AnyOrigin[mut=True]]
comptime U64Ptr = UnsafePointer[UInt64, AnyOrigin[mut=True]]

comptime K0 = UInt64(0xC3A5C85C97CB3127)
comptime K1 = UInt64(0xB492B66FBE98F273)
comptime K2 = UInt64(0x9AE16A3B2F90404F)
comptime C1 = UInt32(0xCC9E2D51)
comptime C2 = UInt32(0x1B873593)


@fieldwise_init
struct Pair:
    var first: UInt64
    var second: UInt64


@fieldwise_init
struct State32:
    var h: UInt32
    var g: UInt32
    var f: UInt32


def fetch32(s: BytePtr, i: Int) -> UInt32:
    return (
        UInt32(s[i])
        | (UInt32(s[i + 1]) << 8)
        | (UInt32(s[i + 2]) << 16)
        | (UInt32(s[i + 3]) << 24)
    )


def fetch64(s: BytePtr, i: Int) -> UInt64:
    return (
        UInt64(s[i])
        | (UInt64(s[i + 1]) << 8)
        | (UInt64(s[i + 2]) << 16)
        | (UInt64(s[i + 3]) << 24)
        | (UInt64(s[i + 4]) << 32)
        | (UInt64(s[i + 5]) << 40)
        | (UInt64(s[i + 6]) << 48)
        | (UInt64(s[i + 7]) << 56)
    )


def bswap32(x: UInt32) -> UInt32:
    return (
        ((x & UInt32(0x000000FF)) << 24)
        | ((x & UInt32(0x0000FF00)) << 8)
        | ((x & UInt32(0x00FF0000)) >> 8)
        | ((x & UInt32(0xFF000000)) >> 24)
    )


def bswap64(x: UInt64) -> UInt64:
    return (
        ((x & UInt64(0x00000000000000FF)) << 56)
        | ((x & UInt64(0x000000000000FF00)) << 40)
        | ((x & UInt64(0x0000000000FF0000)) << 24)
        | ((x & UInt64(0x00000000FF000000)) << 8)
        | ((x & UInt64(0x000000FF00000000)) >> 8)
        | ((x & UInt64(0x0000FF0000000000)) >> 24)
        | ((x & UInt64(0x00FF000000000000)) >> 40)
        | ((x & UInt64(0xFF00000000000000)) >> 56)
    )


def rotate32[shift: Int](value: UInt32) -> UInt32:
    return rotate_bits_right[shift](value)


def rotate[shift: Int](value: UInt64) -> UInt64:
    return rotate_bits_right[shift](value)


def fmix(h0: UInt32) -> UInt32:
    var h = h0
    h ^= h >> 16
    h *= UInt32(0x85EBCA6B)
    h ^= h >> 13
    h *= UInt32(0xC2B2AE35)
    h ^= h >> 16
    return h


def mur(a0: UInt32, h0: UInt32) -> UInt32:
    var a = a0 * C1
    a = rotate32[17](a)
    a *= C2
    var h = h0 ^ a
    h = rotate32[19](h)
    return h * 5 + UInt32(0xE6546B64)


def hash32_len_0_to_4(s: BytePtr, length: Int) -> UInt32:
    var b = UInt32(0)
    var c = UInt32(9)
    for i in range(length):
        var byte = UInt32(s[i])
        var signed_byte = byte
        if byte >= 128:
            signed_byte += UInt32(0xFFFFFF00)
        b = b * C1 + signed_byte
        c ^= b
    return fmix(mur(b, mur(UInt32(length), c)))


def hash32_len_5_to_12(s: BytePtr, length: Int) -> UInt32:
    var a = UInt32(length)
    var b = a * 5
    var c = UInt32(9)
    var d = b
    a += fetch32(s, 0)
    b += fetch32(s, length - 4)
    c += fetch32(s, (length >> 1) & 4)
    return fmix(mur(c, mur(b, mur(a, d))))


def hash32_len_13_to_24(s: BytePtr, length: Int) -> UInt32:
    var a = fetch32(s, -4 + (length >> 1))
    var b = fetch32(s, 4)
    var c = fetch32(s, length - 8)
    var d = fetch32(s, length >> 1)
    var e = fetch32(s, 0)
    var f = fetch32(s, length - 4)
    return fmix(mur(f, mur(e, mur(d, mur(c, mur(b, mur(a, UInt32(length))))))))


@always_inline
def cityhash32_block(s: BytePtr, offset: Int, mut state: State32):
    var a0 = rotate32[17](fetch32(s, offset) * C1) * C2
    var a1 = fetch32(s, offset + 4)
    var a2 = rotate32[17](fetch32(s, offset + 8) * C1) * C2
    var a3 = rotate32[17](fetch32(s, offset + 12) * C1) * C2
    var a4 = fetch32(s, offset + 16)
    var h = state.h ^ a0
    h = rotate32[18](h) * 5 + UInt32(0xE6546B64)
    var f = rotate32[19](state.f + a1) * C1
    var g = state.g + a2
    g = rotate32[18](g) * 5 + UInt32(0xE6546B64)
    h ^= a3 + a1
    h = rotate32[19](h) * 5 + UInt32(0xE6546B64)
    g ^= a4
    g = bswap32(g) * 5
    h += a4 * 5
    h = bswap32(h)
    f += a0
    state.h = f
    state.g = h
    state.f = g


def cityhash32(s: BytePtr, length: Int) -> UInt32:
    if length <= 24:
        if length <= 4:
            return hash32_len_0_to_4(s, length)
        if length <= 12:
            return hash32_len_5_to_12(s, length)
        return hash32_len_13_to_24(s, length)

    var h = UInt32(length)
    var g = C1 * h
    var f = g
    var a0 = rotate32[17](fetch32(s, length - 4) * C1) * C2
    var a1 = rotate32[17](fetch32(s, length - 8) * C1) * C2
    var a2 = rotate32[17](fetch32(s, length - 16) * C1) * C2
    var a3 = rotate32[17](fetch32(s, length - 12) * C1) * C2
    var a4 = rotate32[17](fetch32(s, length - 20) * C1) * C2
    h ^= a0
    h = rotate32[19](h) * 5 + UInt32(0xE6546B64)
    h ^= a2
    h = rotate32[19](h) * 5 + UInt32(0xE6546B64)
    g ^= a1
    g = rotate32[19](g) * 5 + UInt32(0xE6546B64)
    g ^= a3
    g = rotate32[19](g) * 5 + UInt32(0xE6546B64)
    f += a4
    f = rotate32[19](f) * 5 + UInt32(0xE6546B64)
    var offset = 0
    var iters = (length - 1) / 20
    var state = State32(h, g, f)
    while iters >= 2:
        cityhash32_block(s, offset, state)
        cityhash32_block(s, offset + 20, state)
        offset += 40
        iters -= 2
    if iters != 0:
        cityhash32_block(s, offset, state)
    h = state.h
    g = state.g
    f = state.f
    g = rotate32[11](g) * C1
    g = rotate32[17](g) * C1
    f = rotate32[11](f) * C1
    f = rotate32[17](f) * C1
    h = rotate32[19](h + g) * 5 + UInt32(0xE6546B64)
    h = rotate32[17](h) * C1
    h = rotate32[19](h + f) * 5 + UInt32(0xE6546B64)
    return rotate32[17](h) * C1


def shift_mix(value: UInt64) -> UInt64:
    return value ^ (value >> 47)


def hash_len_16_mul(u: UInt64, v: UInt64, mul: UInt64) -> UInt64:
    var a = (u ^ v) * mul
    a ^= a >> 47
    var b = (v ^ a) * mul
    b ^= b >> 47
    return b * mul


def hash_len_16(u: UInt64, v: UInt64) -> UInt64:
    return hash_len_16_mul(u, v, UInt64(0x9DDFEA08EB382D69))


def hash_len_0_to_16(s: BytePtr, offset: Int, length: Int) -> UInt64:
    if length >= 8:
        var mul = K2 + UInt64(length) * 2
        var a = fetch64(s, offset) + K2
        var b = fetch64(s, offset + length - 8)
        var c = rotate[37](b) * mul + a
        var d = (rotate[25](a) + b) * mul
        return hash_len_16_mul(c, d, mul)
    if length >= 4:
        var mul = K2 + UInt64(length) * 2
        var a = UInt64(fetch32(s, offset))
        return hash_len_16_mul(
            UInt64(length) + (a << 3),
            UInt64(fetch32(s, offset + length - 4)),
            mul,
        )
    if length > 0:
        var a = UInt32(s[offset])
        var b = UInt32(s[offset + (length >> 1)])
        var c = UInt32(s[offset + length - 1])
        var y = a + (b << 8)
        var z = UInt32(length) + (c << 2)
        return shift_mix(UInt64(y) * K2 ^ UInt64(z) * K0) * K2
    return K2


def hash_len_17_to_32(s: BytePtr, offset: Int, length: Int) -> UInt64:
    var mul = K2 + UInt64(length) * 2
    var a = fetch64(s, offset) * K1
    var b = fetch64(s, offset + 8)
    var c = fetch64(s, offset + length - 8) * mul
    var d = fetch64(s, offset + length - 16) * K2
    return hash_len_16_mul(
        rotate[43](a + b) + rotate[30](c) + d,
        a + rotate[18](b + K2) + c,
        mul,
    )


def weak_hash(
    w: UInt64,
    x: UInt64,
    y: UInt64,
    z: UInt64,
    a0: UInt64,
    b0: UInt64,
) -> Pair:
    var a = a0 + w
    var b = rotate[21](b0 + a + z)
    var c = a
    a += x
    a += y
    b += rotate[44](a)
    return Pair(a + z, b + c)


def weak_hash_bytes(s: BytePtr, offset: Int, a: UInt64, b: UInt64) -> Pair:
    return weak_hash(
        fetch64(s, offset),
        fetch64(s, offset + 8),
        fetch64(s, offset + 16),
        fetch64(s, offset + 24),
        a,
        b,
    )


def hash_len_33_to_64(s: BytePtr, length: Int) -> UInt64:
    var mul = K2 + UInt64(length) * 2
    var a = fetch64(s, 0) * K2
    var b = fetch64(s, 8)
    var c = fetch64(s, length - 24)
    var d = fetch64(s, length - 32)
    var e = fetch64(s, 16) * K2
    var f = fetch64(s, 24) * 9
    var g = fetch64(s, length - 8)
    var h = fetch64(s, length - 16) * mul
    var u = rotate[43](a + g) + (rotate[30](b) + c) * 9
    var v = ((a + g) ^ d) + f + 1
    var w = bswap64((u + v) * mul) + h
    var x = rotate[42](e + f) + c
    var y = (bswap64((v + w) * mul) + g) * mul
    var z = e + f + c
    a = bswap64((x + z) * mul + y) + b
    b = shift_mix((z + a) * mul + d + h) * mul
    return b + x


def cityhash64(s: BytePtr, original_length: Int) -> UInt64:
    if original_length <= 16:
        return hash_len_0_to_16(s, 0, original_length)
    if original_length <= 32:
        return hash_len_17_to_32(s, 0, original_length)
    if original_length <= 64:
        return hash_len_33_to_64(s, original_length)

    var x = fetch64(s, original_length - 40)
    var y = fetch64(s, original_length - 16) + fetch64(s, original_length - 56)
    var z = hash_len_16(
        fetch64(s, original_length - 48) + UInt64(original_length),
        fetch64(s, original_length - 24),
    )
    var v = weak_hash_bytes(s, original_length - 64, UInt64(original_length), z)
    var w = weak_hash_bytes(s, original_length - 32, y + K1, x)
    x = x * K1 + fetch64(s, 0)
    var length = (original_length - 1) & ~63
    var offset = 0
    while length != 0:
        x = rotate[37](x + y + v.first + fetch64(s, offset + 8)) * K1
        y = rotate[42](y + v.second + fetch64(s, offset + 48)) * K1
        x ^= w.second
        y += v.first + fetch64(s, offset + 40)
        z = rotate[33](z + w.first) * K1
        v = weak_hash_bytes(s, offset, v.second * K1, x + w.first)
        w = weak_hash_bytes(
            s, offset + 32, z + w.second, y + fetch64(s, offset + 16)
        )
        var tmp = z
        z = x
        x = tmp
        offset += 64
        length -= 64
    return hash_len_16(
        hash_len_16(v.first, w.first) + shift_mix(y) * K1 + z,
        hash_len_16(v.second, w.second) + x,
    )


def cityhash64_with_seeds(
    s: BytePtr, length: Int, seed0: UInt64, seed1: UInt64
) -> UInt64:
    return hash_len_16(cityhash64(s, length) - seed0, seed1)


def city_murmur(s: BytePtr, offset0: Int, length0: Int, seed: Pair) -> Pair:
    var a = seed.first
    var b = seed.second
    var c = UInt64(0)
    var d = UInt64(0)
    var offset = offset0
    var length = length0
    if length <= 16:
        a = shift_mix(a * K1) * K1
        c = b * K1 + hash_len_0_to_16(s, offset, length)
        d = shift_mix(a + (fetch64(s, offset) if length >= 8 else c))
    else:
        c = hash_len_16(fetch64(s, offset + length - 8) + K1, a)
        d = hash_len_16(
            b + UInt64(length), c + fetch64(s, offset + length - 16)
        )
        a += d
        while True:
            a ^= shift_mix(fetch64(s, offset) * K1) * K1
            a *= K1
            b ^= a
            c ^= shift_mix(fetch64(s, offset + 8) * K1) * K1
            c *= K1
            d ^= c
            offset += 16
            length -= 16
            if length <= 16:
                break
    a = hash_len_16(a, c)
    b = hash_len_16(d, b)
    return Pair(a ^ b, hash_len_16(b, a))


@always_inline
def cityhash128_with_seed(
    s: BytePtr, offset0: Int, length0: Int, seed: Pair
) -> Pair:
    if length0 < 128:
        return city_murmur(s, offset0, length0, seed)

    var x = seed.first
    var y = seed.second
    var z = UInt64(length0) * K1
    var v = Pair(
        rotate[49](y ^ K1) * K1 + fetch64(s, offset0),
        UInt64(0),
    )
    v.second = rotate[42](v.first) * K1 + fetch64(s, offset0 + 8)
    var w = Pair(
        rotate[35](y + z) * K1 + x,
        rotate[53](x + fetch64(s, offset0 + 88)) * K1,
    )
    var offset = offset0
    var length = length0
    while True:
        x = rotate[37](x + y + v.first + fetch64(s, offset + 8)) * K1
        y = rotate[42](y + v.second + fetch64(s, offset + 48)) * K1
        x ^= w.second
        y += v.first + fetch64(s, offset + 40)
        z = rotate[33](z + w.first) * K1
        v = weak_hash_bytes(s, offset, v.second * K1, x + w.first)
        w = weak_hash_bytes(
            s, offset + 32, z + w.second, y + fetch64(s, offset + 16)
        )
        var tmp = z
        z = x
        x = tmp
        offset += 64

        x = rotate[37](x + y + v.first + fetch64(s, offset + 8)) * K1
        y = rotate[42](y + v.second + fetch64(s, offset + 48)) * K1
        x ^= w.second
        y += v.first + fetch64(s, offset + 40)
        z = rotate[33](z + w.first) * K1
        v = weak_hash_bytes(s, offset, v.second * K1, x + w.first)
        w = weak_hash_bytes(
            s, offset + 32, z + w.second, y + fetch64(s, offset + 16)
        )
        tmp = z
        z = x
        x = tmp
        offset += 64
        length -= 128
        if length < 128:
            break

    x += rotate[49](v.first + z) * K0
    y = y * K0 + rotate[37](w.second)
    z = z * K0 + rotate[27](w.first)
    w.first *= 9
    v.first *= K0
    var tail_done = 0
    while tail_done < length:
        tail_done += 32
        y = rotate[42](x + y) * K0 + v.second
        w.first += fetch64(s, offset + length - tail_done + 16)
        x = x * K0 + w.first
        z += w.second + fetch64(s, offset + length - tail_done)
        w.second += v.first
        v = weak_hash_bytes(
            s,
            offset + length - tail_done,
            v.first + z,
            v.second,
        )
        v.first *= K0
    x = hash_len_16(x, v.first)
    y = hash_len_16(y + z, w.first)
    return Pair(
        hash_len_16(x + v.second, w.second) + y,
        hash_len_16(x + w.second, y + v.second),
    )


def cityhash128(s: BytePtr, length: Int) -> Pair:
    if length >= 16:
        return cityhash128_with_seed(
            s,
            16,
            length - 16,
            Pair(fetch64(s, 0), fetch64(s, 8) + K0),
        )
    return cityhash128_with_seed(s, 0, length, Pair(K0, K1))


@export("mch_cityhash32")
def export_cityhash32(address: Int, length: Int) abi("C") -> UInt32:
    return cityhash32(BytePtr(unsafe_from_address=address), length)


@export("mch_cityhash64")
def export_cityhash64(address: Int, length: Int) abi("C") -> UInt64:
    return cityhash64(BytePtr(unsafe_from_address=address), length)


@export("mch_cityhash64_with_seed")
def export_cityhash64_with_seed(
    address: Int, length: Int, seed: UInt64
) abi("C") -> UInt64:
    return cityhash64_with_seeds(
        BytePtr(unsafe_from_address=address), length, K2, seed
    )


@export("mch_cityhash64_with_seeds")
def export_cityhash64_with_seeds(
    address: Int, length: Int, seed0: UInt64, seed1: UInt64
) abi("C") -> UInt64:
    return cityhash64_with_seeds(
        BytePtr(unsafe_from_address=address), length, seed0, seed1
    )


@export("mch_cityhash128")
def export_cityhash128(address: Int, length: Int, result_address: Int) abi("C"):
    var result = cityhash128(BytePtr(unsafe_from_address=address), length)
    var dst = U64Ptr(unsafe_from_address=result_address)
    dst[0] = result.first
    dst[1] = result.second


@export("mch_cityhash128_with_seed")
def export_cityhash128_with_seed(
    address: Int,
    length: Int,
    seed_first: UInt64,
    seed_second: UInt64,
    result_address: Int,
) abi("C"):
    var result = cityhash128_with_seed(
        BytePtr(unsafe_from_address=address),
        0,
        length,
        Pair(seed_first, seed_second),
    )
    var dst = U64Ptr(unsafe_from_address=result_address)
    dst[0] = result.first
    dst[1] = result.second
