<?php

namespace App\Http\Controllers;

use App\Models\Visit;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

class StatsController extends Controller
{
    public function loginForm(): View
    {
        return view('stats-login');
    }

    public function login(Request $request): RedirectResponse
    {
        $data = $request->validate([
            'password' => ['required', 'string'],
        ]);

        if (! hash_equals((string) config('visitor.stats_password'), $data['password'])) {
            return back()->withErrors([
                'password' => 'Invalid password',
            ]);
        }

        $request->session()->put('visitor_stats_authorized', true);

        return redirect()->route('stats.index');
    }

    public function logout(Request $request): RedirectResponse
    {
        $request->session()->forget('visitor_stats_authorized');

        return redirect()->route('stats.login');
    }

    public function index(): View
    {
        $hourly = Visit::query()
            ->selectRaw("strftime('%Y-%m-%d %H:00:00', visited_at) as hour, COUNT(DISTINCT visitor_id) as visits")
            ->groupBy('hour')
            ->orderBy('hour')
            ->get()
            ->map(fn ($row) => [
                'hour' => $row->hour,
                'visits' => (int) $row->visits,
            ]);

        $cities = Visit::query()
            ->selectRaw("COALESCE(NULLIF(city, ''), 'Unknown') as city, COUNT(*) as visits")
            ->groupBy('city')
            ->orderByDesc('visits')
            ->get()
            ->map(fn ($row) => [
                'city' => $row->city,
                'visits' => (int) $row->visits,
            ]);

        return view('stats', [
            'hourly' => $hourly,
            'cities' => $cities,
        ]);
    }
}
