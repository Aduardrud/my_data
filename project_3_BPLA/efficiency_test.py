import timeit

from missions import SurveyNavigator, OrbitNavigator
# Тест производительности SurveyNavigator
setup_survey = SurveyNavigator
mission = SurveyNavigator(boxsize=30, stripewidth=10, altitude=30, velocity=10)

survey_start_time = timeit.timeit("mission.start()", setup=setup_survey, number=10)
survey_landed_time = timeit.timeit("mission.landed()", setup=setup_survey, number=10)
print(f"SurveyNavigator start() time: {survey_start_time/10:.6f} seconds")
print(f"SurveyNavigator landed() time: {survey_landed_time/10:.6f} seconds")

# Тест производительности OrbitNavigator
setup_orbit = OrbitNavigator
mission = OrbitNavigator(radius=50, altitude=30, velocity=10, iterations=1, center=[1, 0], snapshots=5)

orbit_start_time = timeit.timeit("mission.start()", setup=setup_orbit, number=10)
orbit_landed_time = timeit.timeit("mission.landed()", setup=setup_orbit, number=10)
print(f"OrbitNavigator start() time: {orbit_start_time/10:.6f} seconds")
print(f"OrbitNavigator landed() time: {orbit_landed_time/10:.6f} seconds")
