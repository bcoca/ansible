#!/usr/bin/perl
use strict;
use JSON::PP;
use Data::Dumper;

# by default a module will receive one argument: a path to a temporary file containing key - value pairs. example:
#
# var1=value1 var2=value2

# prep return
my %results = (failed  => JSON::PP::false, changed => JSON::PP::false, msg => 'pong');

# internal options
my %options;

# open args file and slurp it
open my $a, "<", $ARGV[0] or die "Could not open $ARGV[0]\n";
my $args = <$a>;

# parse k=v pairs
my @list = $args =~ /([^=\s]*=(?:'[^=]*'|[^\s]*))[\s]*/g;

# consume k=v paris and add to results, unless they are internal optoins
while (my $keyvalue = pop @list) {
    my ($key, $value) = $keyvalue =~ /^([^=]+)=(.*)$/;
    if ($key =~ /_ansible/) {
		$options{$key} = $value;
	} else {
		$results{$key} = $value unless $key =~ /_ansible/;
	}
}

#### we would do other work here ####
# we would check options for checkmode/diff mode/etc

# return JSON formatted string
print encode_json(\%results);
