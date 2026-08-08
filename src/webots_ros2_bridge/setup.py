from setuptools import find_packages, setup
from glob import glob
package_name="webots_ros2_bridge"
setup(name=package_name,version="1.0.1",packages=find_packages(),data_files=[("share/ament_index/resource_index/packages",["resource/"+package_name]),("share/"+package_name,["package.xml"]),("share/"+package_name+"/launch",glob("launch/*.py")),("share/"+package_name+"/config",glob("config/*"))],install_requires=["setuptools"],zip_safe=True,maintainer="Webots 5v5 Brain Simulator contributors",maintainer_email="sim@example.com",description="Webots and ROS 2 local relay bridge",license="Apache-2.0",entry_points={"console_scripts":["bridge_node=webots_ros2_bridge.bridge_node:main"]})
