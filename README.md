# gbp-testkit

Gentoo Build Publisher testing tools.

## Description

It seems like most of the new functionality in [Gentoo Build
Publisher](https://github.com/enku/gentoo-build-publisher) is coming on the
form of plugins. When writing tests for plugins I find myself copying bits and
pieces from Gentoo Build Publisher's tests directory. Such things as fixtures,
mocks, utilities, etc. This is not very
[DRY](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself), so the desire to
have a third-party package that plugins and GBP itself can use as a library
arose. Hence gbp-testkit.

The gbp-testkit package is (will be) useful to GBP plugin developers as well
as the core Gentoo Build Publisher  and
[gbpcli](https://github.com/enku/gbpcli) projects. It (will) supports server
and client-size operations, GraphQL, taking screenshots and more. The testkit
itself borrows from my other testing package,
[unittest-fixtures](https://github.com/enku/unittest-fixtures).
