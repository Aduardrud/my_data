import unittest
from unittest.mock import patch, call
import airsim
from missions import SurveyNavigator, OrbitNavigator, Position

class TestSurveyNavigator(unittest.TestCase):
    def test_init_with_missing_parameters(self):
        with self.assertRaises(ValueError):
            SurveyNavigator()

    @patch('airsim.MultirotorClient')
    def test_start(self, mock_client):
        # Arrange
        mock_client_instance = mock_client.return_value
        mock_client_instance.getMultirotorState.return_value.landed_state = airsim.LandedState.Landed
        mock_client_instance.moveToPositionAsync.return_value.join.return_value = None
        mock_client_instance.moveOnPathAsync.return_value.join.return_value = None
        mission = SurveyNavigator(boxsize=30, stripewidth=10, altitude=30, velocity=10)

        # Act
        mission.start()

        # Assert
        self.assertEqual(mock_client_instance.armDisarm.call_count, 1)
        self.assertEqual(mock_client_instance.moveToPositionAsync.call_count, 2)
        self.assertEqual(mock_client_instance.moveOnPathAsync.call_count, 1)

    @patch('airsim.MultirotorClient')
    def test_landed(self, mock_client):
        # Arrange
        mock_client_instance = mock_client.return_value
        mock_client_instance.getMultirotorState.return_value.kinematics_estimated.position.z_val = -10
        mission = SurveyNavigator(boxsize=30, stripewidth=10, altitude=30, velocity=10)

        # Act
        mission.landed()

        # Assert
        self.assertEqual(mock_client_instance.hoverAsync.call_count, 1)
        self.assertEqual(mock_client_instance.moveToPositionAsync.call_count, 1)
        self.assertEqual(mock_client_instance.landAsync.call_count, 1)
        self.assertEqual(mock_client_instance.armDisarm.call_count, 1)
        self.assertEqual(mock_client_instance.enableApiControl.call_count, 1)

class TestOrbitNavigator(unittest.TestCase):
    def test_1_init_with_missing_parameters(self):
        with self.assertRaises(ValueError):
            OrbitNavigator()

    @patch('airsim.MultirotorClient')
    def test_2_start(self, mock_client):
        # Arrange
        mock_client_instance = mock_client.return_value
        mock_client_instance.getMultirotorState.return_value.kinematics_estimated.position = Position(airsim.Vector3r(0, 0, 0))
        mock_client_instance.getMultirotorState.return_value.landed_state = airsim.LandedState.Landed
        mock_client_instance.takeoffAsync.return_value.join.return_value = None
        mock_client_instance.moveToPositionAsync.return_value.join.return_value = None
        mock_client_instance.moveByVelocityZAsync.return_value.join.return_value = None
        mission = OrbitNavigator(radius=50, altitude=30, velocity=10, iterations=1, center=[1, 0], snapshots=5)

        # Act
        mission.start()

        # Assert
        self.assertEqual(mock_client_instance.armDisarm.call_count, 1)
        self.assertEqual(mock_client_instance.takeoffAsync.call_count, 1)
        self.assertEqual(mock_client_instance.moveToPositionAsync.call_count, 1)
        self.assertEqual(mock_client_instance.moveByVelocityZAsync.call_count, 1)

    @patch('airsim.MultirotorClient')
    def test_3_landed(self, mock_client):
        # Arrange
        mock_client_instance = mock_client.return_value
        mock_client_instance.getMultirotorState.return_value.kinematics_estimated.position.z_val = -10
        mission = OrbitNavigator(radius=50, altitude=30, velocity=10, iterations=1, center=[1, 0], snapshots=5)

        # Act
        mission.landed()

        # Assert
        self.assertEqual(mock_client_instance.hoverAsync.call_count, 1)
        self.assertEqual(mock_client_instance.moveToPositionAsync.call_count, 1)
        self.assertEqual(mock_client_instance.landAsync.call_count, 1)
        self.assertEqual(mock_client_instance.armDisarm.call_count, 1)
        self.assertEqual(mock_client_instance.enableApiControl.call_count, 1)

if __name__ == '__main__':
    unittest.main()