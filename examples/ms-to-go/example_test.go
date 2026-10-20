package ms_test

import (
	"fmt"

	"github.com/agentporter-examples/ms"
)

func ExampleParse() {
	for _, s := range []string{"2 days", "1d", "10h", "2.5 hrs", "2h", "1m", "5s", "1y", "100", "-3 days", "-1h", "-200"} {
		n, _ := ms.Parse(s)
		fmt.Printf("%s = %.0f\n", s, n)
	}
	_, ok := ms.Parse("soon")
	fmt.Println("soon is a duration:", ok)
	// Output:
	// 2 days = 172800000
	// 1d = 86400000
	// 10h = 36000000
	// 2.5 hrs = 9000000
	// 2h = 7200000
	// 1m = 60000
	// 5s = 5000
	// 1y = 31557600000
	// 100 = 100
	// -3 days = -259200000
	// -1h = -3600000
	// -200 = -200
	// soon is a duration: false
}

func ExampleFormat() {
	tenHours, _ := ms.Parse("10 hours")
	for _, n := range []float64{60000, 2 * 60000, -3 * 60000, tenHours} {
		s, _ := ms.Format(n)
		fmt.Println(s)
	}
	// Output:
	// 1m
	// 2m
	// -3m
	// 10h
}

func ExampleFormatLong() {
	tenHours, _ := ms.Parse("10 hours")
	for _, n := range []float64{60000, 2 * 60000, -3 * 60000, tenHours} {
		s, _ := ms.FormatLong(n)
		fmt.Println(s)
	}
	// Output:
	// 1 minute
	// 2 minutes
	// -3 minutes
	// 10 hours
}
